pipeline {
    agent any

    triggers {
        // Poll SCM every 2 minutes for changes
        pollSCM('H/2 * * * *')
        // Alternative: Use webhook trigger (recommended)
        // githubPush()
    }

    environment {
        // Application configuration
        PYTHON_VERSION = '3.11'

        // Docker configuration
        DOCKER_REGISTRY = 'your-artifactory-server.com:8082'
        DOCKER_REPO = 'docker-local'

        // Artifactory credentials
        ARTIFACTORY_CREDS = credentials('artifactory-credentials')

        // Build configuration
        BUILD_VERSION = "${BUILD_NUMBER}"
        COMMIT_HASH = "${GIT_COMMIT.take(8)}"

        // Multi-app configuration - will be auto-discovered
        PREDEFINED_APP_FOLDERS = 'app1,app2,app3'
        AUTO_DISCOVER_APPS = 'true'
    }

    stages {
        stage('Checkout') {
            steps {
                echo "[CHECKOUT] Checking out repository..."
                checkout scm

                // Get commit information
                script {
                    env.GIT_COMMIT_MSG = bat(
                        script: '@git log -1 --pretty=%%B',
                        returnStdout: true
                    ).trim()

                    env.GIT_AUTHOR = bat(
                        script: '@git log -1 --pretty=%%an',
                        returnStdout: true
                    ).trim()

                    env.GIT_COMMIT_HASH = bat(
                        script: '@git rev-parse HEAD',
                        returnStdout: true
                    ).trim()
                }

                echo "[COMMIT] ${env.GIT_COMMIT_HASH}"
                echo "[AUTHOR] ${env.GIT_AUTHOR}"
                echo "[MESSAGE] ${env.GIT_COMMIT_MSG}"
            }
        }
        
        stage('Discover and Detect App Changes') {
            steps {
                script {
                    echo "[DISCOVERY] Auto-discovering application folders..."

                    // Auto-discover app folders
                    def discoveredApps = []
                    if (env.AUTO_DISCOVER_APPS == 'true') {
                        def appDirs = powershell(
                            script: 'Get-ChildItem -Directory | Where-Object { $_.Name -match "^app\\d+$" } | ForEach-Object { $_.Name }',
                            returnStdout: true
                        ).trim()

                        if (appDirs) {
                            discoveredApps = appDirs.split('\n').findAll { it.trim() }
                            echo "[AUTO_DISCOVERED] Found app folders: ${discoveredApps.join(', ')}"
                        }
                    }

                    // Combine predefined and discovered apps
                    def predefinedApps = env.PREDEFINED_APP_FOLDERS.split(',')
                    def allAppFolders = (predefinedApps + discoveredApps).unique()

                    echo "[MONITORING] All application folders: ${allAppFolders.join(', ')}"
                    env.ALL_APP_FOLDERS = allAppFolders.join(',')

                    echo "[DETECTION] Scanning for changes in application folders..."

                    // Get list of changed files in the current commit
                    def output = bat(
                        script: '@git diff-tree --no-commit-id --name-only -r HEAD',
                        returnStdout: true
                    ).trim()
                    def changedFiles = output.split('\n')

                    // Define app folders to monitor
                    def appFolders = allAppFolders
                    def appsWithChanges = []
                    def appChangeDetails = [:]

                    // Check each app folder for changes
                    appFolders.each { appFolder ->
                        echo "[CHECKING] Scanning ${appFolder}/ for changes..."

                        // Find files changed in this app folder
                        def appChangedFiles = changedFiles.findAll { file ->
                            file.startsWith("${appFolder}/")
                        }

                        if (appChangedFiles.size() > 0) {
                            echo "[CHANGES] Found ${appChangedFiles.size()} changed file(s) in ${appFolder}/"
                            appsWithChanges.add(appFolder)

                            // Categorize changes
                            def pythonFiles = appChangedFiles.findAll { it.endsWith('.py') }
                            def dockerfileChanged = appChangedFiles.any { it.endsWith('/Dockerfile') }
                            def requirementsChanged = appChangedFiles.any { it.endsWith('/requirements.txt') }

                            appChangeDetails[appFolder] = [
                                python_files: pythonFiles,
                                dockerfile_changed: dockerfileChanged,
                                requirements_changed: requirementsChanged,
                                all_files: appChangedFiles
                            ]

                            echo "[PYTHON_FILES] ${appFolder}: ${pythonFiles.size()} Python files"
                            echo "[DOCKER_CONFIG] ${appFolder}: Dockerfile changed: ${dockerfileChanged}"
                            echo "[REQUIREMENTS] ${appFolder}: requirements.txt changed: ${requirementsChanged}"

                            pythonFiles.each { file ->
                                echo "[FILE] ${file}"
                            }
                        } else {
                            echo "[NO_CHANGES] No changes detected in ${appFolder}/"
                        }
                    }

                    // Store results for next stages
                    if (appsWithChanges.size() > 0) {
                        env.APPS_WITH_CHANGES = appsWithChanges.join(',')
                        env.NEEDS_MULTI_BUILD = 'true'

                        echo "[SUMMARY] Applications requiring rebuild:"
                        appsWithChanges.each { app ->
                            echo "[BUILD_REQUIRED] ${app}"
                        }
                    } else {
                        echo "[INFO] No application folders have changes requiring rebuild"
                        env.APPS_WITH_CHANGES = ''
                        env.NEEDS_MULTI_BUILD = 'false'
                    }

                    // Store detailed change information as JSON for later stages
                    def changeDetailsJson = groovy.json.JsonBuilder(appChangeDetails).toString()
                    writeFile file: 'app_changes.json', text: changeDetailsJson

                    echo "[STORED] Change details saved for build stages"
                }
            }
        }
        
        stage('Validate and Filter Applications') {
            when {
                environment name: 'NEEDS_MULTI_BUILD', value: 'true'
            }
            steps {
                script {
                    echo "[VALIDATION] Validating applications with changes..."

                    def appsToValidate = env.APPS_WITH_CHANGES.split(',')
                    def validAppsForBuild = []
                    def incompleteApps = []

                    appsToValidate.each { appName ->
                        echo "[VALIDATING] Application: ${appName}"

                        def isValidForBuild = true
                        def validationIssues = []

                        // Check if Dockerfile exists
                        def dockerfilePath = "${appName}/Dockerfile"
                        if (fileExists(dockerfilePath)) {
                            echo "[DOCKERFILE] Found: ${dockerfilePath}"
                        } else {
                            echo "[MISSING] Dockerfile not found: ${dockerfilePath}"
                            validationIssues.add("Missing Dockerfile")
                            isValidForBuild = false
                        }

                        // Check if requirements.txt exists
                        def requirementsPath = "${appName}/requirements.txt"
                        if (fileExists(requirementsPath)) {
                            echo "[REQUIREMENTS] Found: ${requirementsPath}"
                            def reqContent = readFile(requirementsPath)
                            def reqLines = reqContent.split('\n').findAll { it.trim() }
                            echo "[DEPENDENCIES] ${appName} has ${reqLines.size()} dependencies"
                        } else {
                            echo "[MISSING] requirements.txt not found: ${requirementsPath}"
                            validationIssues.add("Missing requirements.txt")
                            // Note: requirements.txt is optional, don't fail build
                        }

                        // Validate Python files in the app
                        def pythonFiles = powershell(
                            script: "Get-ChildItem -Path './${appName}' -Filter '*.py' -Recurse | ForEach-Object { \$_.FullName.Replace((Get-Location).Path + '\\', '') }",
                            returnStdout: true
                        ).trim()

                        if (pythonFiles) {
                            def fileCount = 0
                            def syntaxErrors = []

                            pythonFiles.split('\n').each { file ->
                                if (file.trim()) {
                                    fileCount++
                                    echo "[PYTHON_FILE] ${file.trim()}"

                                    // Validate Python syntax (non-blocking)
                                    try {
                                        bat(script: "@python -m py_compile \"${file.trim()}\" 2>&1", returnStdout: true)
                                        echo "[SYNTAX_OK] ${file.trim()}"
                                    } catch (Exception e) {
                                        echo "[SYNTAX_ERROR] ${file.trim()}: ${e.message}"
                                        syntaxErrors.add(file.trim())
                                    }
                                }
                            }

                            echo "[VALIDATED] ${appName}: ${fileCount} Python files found"

                            if (syntaxErrors.size() > 0) {
                                echo "[WARNING] ${appName} has ${syntaxErrors.size()} files with syntax errors"
                                validationIssues.add("Python syntax errors in ${syntaxErrors.size()} files")
                                // Note: Syntax errors are warnings, not build blockers
                            }
                        } else {
                            echo "[WARNING] No Python files found in ${appName}"
                            validationIssues.add("No Python files found")
                        }

                        // Categorize app based on validation results
                        if (isValidForBuild) {
                            validAppsForBuild.add(appName)
                            echo "[READY_FOR_BUILD] ${appName} - Docker build will proceed"
                        } else {
                            incompleteApps.add(appName)
                            echo "[INCOMPLETE] ${appName} - Docker build will be skipped"
                            echo "[ISSUES] ${appName}: ${validationIssues.join(', ')}"
                        }
                    }

                    // Store results for next stages
                    env.VALID_APPS_FOR_BUILD = validAppsForBuild.join(',')
                    env.INCOMPLETE_APPS = incompleteApps.join(',')

                    echo "[SUMMARY] Validation Results:"
                    echo "[BUILD_READY] ${validAppsForBuild.size()} apps ready for Docker build: ${validAppsForBuild.join(', ')}"
                    echo "[INCOMPLETE] ${incompleteApps.size()} apps with missing configuration: ${incompleteApps.join(', ')}"

                    // Update build flag based on valid apps
                    if (validAppsForBuild.size() > 0) {
                        env.HAS_VALID_APPS_FOR_BUILD = 'true'
                        echo "[PROCEED] Docker build will proceed for valid applications"
                    } else {
                        env.HAS_VALID_APPS_FOR_BUILD = 'false'
                        echo "[SKIP] No applications are ready for Docker build"
                    }
                }
            }
        }
        
        stage('Build Docker Images') {
            when {
                allOf {
                    environment name: 'NEEDS_MULTI_BUILD', value: 'true'
                    environment name: 'HAS_VALID_APPS_FOR_BUILD', value: 'true'
                }
            }
            steps {
                script {
                    echo "[DOCKER] Building Docker images for validated applications..."

                    def appsToProcess = env.VALID_APPS_FOR_BUILD.split(',')
                    def buildJobs = [:]

                    if (env.INCOMPLETE_APPS && env.INCOMPLETE_APPS != '') {
                        echo "[SKIPPING] Apps with incomplete configuration: ${env.INCOMPLETE_APPS}"
                    }

                    // Create parallel build jobs for each app
                    appsToProcess.each { appName ->
                        buildJobs[appName] = {
                            echo "[BUILD_START] Building ${appName} Docker image..."

                            def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${appName}"
                            def imageTag = "${env.BUILD_VERSION}-${env.COMMIT_HASH}"

                            try {
                                // Build Docker image from app-specific Dockerfile
                                bat "docker build -t ${imageName}:${imageTag} -f ${appName}/Dockerfile ${appName}/"
                                bat "docker tag ${imageName}:${imageTag} ${imageName}:latest"

                                echo "[SUCCESS] ${appName} Docker image built successfully"
                                echo "[IMAGE] ${imageName}:${imageTag}"
                                echo "[IMAGE] ${imageName}:latest"

                                // Store success status
                                writeFile file: "${appName}_build_success.txt", text: "true"

                            } catch (Exception e) {
                                echo "[ERROR] ${appName} Docker build failed: ${e.message}"
                                writeFile file: "${appName}_build_success.txt", text: "false"
                                error("Docker build failed for ${appName}")
                            }
                        }
                    }

                    // Execute builds in parallel
                    echo "[PARALLEL] Starting parallel Docker builds..."
                    parallel buildJobs

                    // Verify all builds succeeded
                    def allBuildsSuccessful = true
                    appsToProcess.each { appName ->
                        def buildStatus = readFile("${appName}_build_success.txt").trim()
                        if (buildStatus != 'true') {
                            allBuildsSuccessful = false
                            echo "[FAILED] ${appName} build was not successful"
                        }
                    }

                    env.ALL_BUILDS_SUCCESS = allBuildsSuccessful.toString()
                    echo "[BUILD_RESULT] All builds successful: ${allBuildsSuccessful}"
                }
            }
        }

        stage('Build Docker Images') {
            when {
                environment name: 'NEEDS_MULTI_BUILD', value: 'true'
            }
            steps {
                script {
                    echo "[DOCKER] Building Docker images for changed applications..."

                    def appsToProcess = env.APPS_WITH_CHANGES.split(',')
                    def buildJobs = [:]

                    // Create parallel build jobs for each app
                    appsToProcess.each { appName ->
                        buildJobs[appName] = {
                            echo "[BUILD_START] Building ${appName} Docker image..."

                            def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${appName}"
                            def imageTag = "${env.BUILD_VERSION}-${env.COMMIT_HASH}"

                            try {
                                // Build Docker image from app-specific Dockerfile
                                bat "docker build -t ${imageName}:${imageTag} -f ${appName}/Dockerfile ${appName}/"
                                bat "docker tag ${imageName}:${imageTag} ${imageName}:latest"

                                echo "[SUCCESS] ${appName} Docker image built successfully"
                                echo "[IMAGE] ${imageName}:${imageTag}"
                                echo "[IMAGE] ${imageName}:latest"

                                // Store success status
                                writeFile file: "${appName}_build_success.txt", text: "true"

                            } catch (Exception e) {
                                echo "[ERROR] ${appName} Docker build failed: ${e.message}"
                                writeFile file: "${appName}_build_success.txt", text: "false"
                                error("Docker build failed for ${appName}")
                            }
                        }
                    }

                    // Execute builds in parallel
                    echo "[PARALLEL] Starting parallel Docker builds..."
                    parallel buildJobs

                    // Verify all builds succeeded
                    def allBuildsSuccessful = true
                    appsToProcess.each { appName ->
                        def buildStatus = readFile("${appName}_build_success.txt").trim()
                        if (buildStatus != 'true') {
                            allBuildsSuccessful = false
                            echo "[FAILED] ${appName} build was not successful"
                        }
                    }

                    env.ALL_BUILDS_SUCCESS = allBuildsSuccessful.toString()
                    echo "[BUILD_RESULT] All builds successful: ${allBuildsSuccessful}"
                }
            }
        }

        stage('Push to Artifactory') {
            when {
                allOf {
                    environment name: 'NEEDS_MULTI_BUILD', value: 'true'
                    environment name: 'HAS_VALID_APPS_FOR_BUILD', value: 'true'
                    environment name: 'ALL_BUILDS_SUCCESS', value: 'true'
                }
            }
            steps {
                script {
                    echo "[ARTIFACTORY] Pushing Docker images to Artifactory..."

                    def appsToProcess = env.VALID_APPS_FOR_BUILD.split(',')
                    def pushJobs = [:]

                    // Login to Artifactory once
                    try {
                        bat """
                            docker login ${env.DOCKER_REGISTRY} -u ${env.ARTIFACTORY_CREDS_USR} -p ${env.ARTIFACTORY_CREDS_PSW}
                        """
                        echo "[LOGIN] Successfully logged into Artifactory"

                        // Create parallel push jobs for each app
                        appsToProcess.each { appName ->
                            pushJobs[appName] = {
                                echo "[PUSH_START] Pushing ${appName} to Artifactory..."

                                def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${appName}"
                                def imageTag = "${env.BUILD_VERSION}-${env.COMMIT_HASH}"

                                try {
                                    // Push both tagged and latest versions
                                    bat "docker push ${imageName}:${imageTag}"
                                    bat "docker push ${imageName}:latest"

                                    echo "[SUCCESS] ${appName} images pushed successfully"
                                    echo "[PUSHED] ${imageName}:${imageTag}"
                                    echo "[PUSHED] ${imageName}:latest"

                                    // Store push success status
                                    writeFile file: "${appName}_push_success.txt", text: "true"

                                } catch (Exception e) {
                                    echo "[ERROR] ${appName} push failed: ${e.message}"
                                    writeFile file: "${appName}_push_success.txt", text: "false"
                                    error("Artifactory push failed for ${appName}")
                                }
                            }
                        }

                        // Execute pushes in parallel
                        echo "[PARALLEL] Starting parallel Artifactory pushes..."
                        parallel pushJobs

                        // Verify all pushes succeeded
                        def allPushesSuccessful = true
                        appsToProcess.each { appName ->
                            def pushStatus = readFile("${appName}_push_success.txt").trim()
                            if (pushStatus != 'true') {
                                allPushesSuccessful = false
                                echo "[FAILED] ${appName} push was not successful"
                            }
                        }

                        env.ALL_PUSHES_SUCCESS = allPushesSuccessful.toString()
                        echo "[PUSH_RESULT] All pushes successful: ${allPushesSuccessful}"

                    } catch (Exception e) {
                        echo "[ERROR] Artifactory operations failed: ${e.message}"
                        env.ALL_PUSHES_SUCCESS = 'false'
                        error("Artifactory push failed")
                    } finally {
                        // Logout from Artifactory
                        bat "docker logout ${env.DOCKER_REGISTRY}"
                        echo "[LOGOUT] Logged out from Artifactory"
                    }
                }
            }
        }

        stage('Summary') {
            steps {
                script {
                    echo "[SUMMARY] MULTI-APP CI/CD BUILD SUMMARY"
                    echo "=" * 60
                    echo "[REPOSITORY] ${env.GIT_URL ?: 'Local repository'}"
                    echo "[BRANCH] ${env.GIT_BRANCH ?: 'Unknown'}"
                    echo "[COMMIT] ${env.GIT_COMMIT_HASH}"
                    echo "[AUTHOR] ${env.GIT_AUTHOR}"
                    echo "[MESSAGE] ${env.GIT_COMMIT_MSG}"
                    echo "[BUILD_NUMBER] ${env.BUILD_NUMBER}"
                    echo "[MONITORED_APPS] ${env.ALL_APP_FOLDERS}"

                    if (env.NEEDS_MULTI_BUILD == 'true') {
                        echo "[APPS_WITH_CHANGES] ${env.APPS_WITH_CHANGES}"

                        if (env.VALID_APPS_FOR_BUILD && env.VALID_APPS_FOR_BUILD != '') {
                            echo "[APPS_BUILT] ${env.VALID_APPS_FOR_BUILD}"
                            def appsProcessed = env.VALID_APPS_FOR_BUILD.split(',')
                            appsProcessed.each { appName ->
                                def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${appName}"
                                def imageTag = "${env.BUILD_VERSION}-${env.COMMIT_HASH}"

                                echo "[APP] ${appName}:"
                                echo "  [IMAGE] ${imageName}:${imageTag}"
                                echo "  [IMAGE] ${imageName}:latest"

                                // Check build status
                                try {
                                    def buildStatus = readFile("${appName}_build_success.txt").trim()
                                    echo "  [BUILD_STATUS] ${buildStatus == 'true' ? 'SUCCESS' : 'FAILED'}"
                                } catch (Exception e) {
                                    echo "  [BUILD_STATUS] UNKNOWN"
                                }

                                // Check push status
                                try {
                                    def pushStatus = readFile("${appName}_push_success.txt").trim()
                                    echo "  [PUSH_STATUS] ${pushStatus == 'true' ? 'SUCCESS' : 'FAILED'}"
                                } catch (Exception e) {
                                    echo "  [PUSH_STATUS] UNKNOWN"
                                }
                            }

                            if (env.ALL_BUILDS_SUCCESS == 'true') {
                                echo "[OVERALL_BUILD] SUCCESS - All valid applications built successfully"
                            } else {
                                echo "[OVERALL_BUILD] FAILED - Some applications failed to build"
                            }

                            if (env.ALL_PUSHES_SUCCESS == 'true') {
                                echo "[OVERALL_PUSH] SUCCESS - All images pushed to Artifactory"
                            } else {
                                echo "[OVERALL_PUSH] FAILED - Some images failed to push"
                            }
                        } else {
                            echo "[NO_VALID_APPS] No applications were ready for Docker build"
                        }

                        // Report incomplete apps
                        if (env.INCOMPLETE_APPS && env.INCOMPLETE_APPS != '') {
                            echo "[INCOMPLETE_APPS] ${env.INCOMPLETE_APPS}"
                            def incompleteApps = env.INCOMPLETE_APPS.split(',')
                            incompleteApps.each { appName ->
                                echo "[SKIPPED] ${appName} - Missing Docker configuration"
                            }
                            echo "[INFO] Add Dockerfile to incomplete apps to enable Docker builds"
                        }
                    } else {
                        echo "[APP_CHANGES] NO - No application folders have changes"
                        echo "[INFO] This commit doesn't affect any monitored application folders"
                        echo "[SKIPPED] Docker build and Artifactory push skipped"
                    }

                    echo "[COMPLETED] Build finished at: ${new Date()}"
                }
            }
        }
    }

    post {
        always {
            echo "[CLEANUP] Cleaning up workspace..."
            // Add any cleanup steps here
        }
        success {
            echo "[SUCCESS] Pipeline completed successfully!"
        }
        failure {
            echo "[FAILURE] Pipeline failed!"
        }
        changed {
            echo "[CHANGED] Pipeline status changed from previous run"
        }
    }
}
