pipeline {
    agent any

    triggers {
        // Poll SCM every 2 minutes for changes
        //pollSCM('H/2 * * * *')
        // Alternative: Use webhook trigger (recommended)
        githubPush()
    }

    environment {
        // Application configuration
        PYTHON_VERSION = '3.11'

        // Docker configuration
        DOCKER_REGISTRY = 'trialqlk1tc.jfrog.io'
        DOCKER_REPO = 'dockertest-docker'

        // Artifactory credentials (update ID to match your Jenkins credentials)
        ARTIFACTORY_CREDS = credentials('artifactory-credentials')

        // Build configuration
        BUILD_VERSION = "${BUILD_NUMBER}"
        COMMIT_HASH = "${GIT_COMMIT.take(8)}"

        // Universal folder discovery - no naming restrictions
        DISCOVER_ALL_FOLDERS = 'true'
        PYTHON_FILE_EXTENSIONS = '*.py'
    }

    stages {
        stage('Checkout') {
            steps {
                echo "[CHECKOUT] Checking out repository..."
                checkout scm

                // Get commit information
                script {
                    try {
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

                        echo "[GIT_INFO] Successfully retrieved git commit information"
                    } catch (Exception e) {
                        echo "[GIT_WARNING] Could not retrieve git information: ${e.message}"
                        env.GIT_COMMIT_MSG = "Git information unavailable"
                        env.GIT_AUTHOR = "Unknown"
                        env.GIT_COMMIT_HASH = "unknown-${BUILD_NUMBER}"
                    }
                }

                echo "[COMMIT] ${env.GIT_COMMIT_HASH}"
                echo "[AUTHOR] ${env.GIT_AUTHOR}"
                echo "[MESSAGE] ${env.GIT_COMMIT_MSG}"
            }
        }
        
        stage('Universal Folder Discovery') {
            steps {
                script {
                    echo "[DISCOVERY] Scanning repository for all folders with Python files..."

                    // Discover ALL root-level folders (no naming restrictions)
                    def allRootFolders = []
                    try {
                        def rootDirs = bat(
                            script: '@for /d %%i in (*) do @echo %%i',
                            returnStdout: true
                        ).trim()

                        if (rootDirs) {
                            allRootFolders = rootDirs.split('\n').findAll { it.trim() }
                            echo "[ROOT_FOLDERS] Found ${allRootFolders.size()} root-level folders: ${allRootFolders.join(', ')}"
                        } else {
                            echo "[INFO] No root-level folders found in repository"
                        }
                    } catch (Exception e) {
                        echo "[WARNING] Could not scan for folders: ${e.message}"
                        allRootFolders = []
                    }

                    // Filter folders that contain Python files (at any depth)
                    def foldersWithPython = []
                    allRootFolders.each { folderName ->
                        echo "[SCANNING] Checking ${folderName}/ for Python files..."

                        def pythonFiles = ""
                        try {
                            // Use Jenkins native approach - scan known patterns
                            if (fileExists("${folderName}")) {
                                // Check common Python file locations
                                def foundFiles = []

                                // Check root level Python files
                                def rootFiles = findFiles(glob: "${folderName}/*.py")
                                rootFiles.each { file ->
                                    foundFiles.add(file.path)
                                }

                                // Check subdirectories for Python files
                                def subFiles = findFiles(glob: "${folderName}/**/*.py")
                                subFiles.each { file ->
                                    foundFiles.add(file.path)
                                }

                                if (foundFiles.size() > 0) {
                                    pythonFiles = foundFiles.join('\n')
                                } else {
                                    pythonFiles = ""
                                }
                            } else {
                                pythonFiles = ""
                            }
                        } catch (Exception e) {
                            // No Python files found or folder doesn't exist
                            pythonFiles = ""
                        }

                        if (pythonFiles && pythonFiles != "") {
                            def fileList = pythonFiles.split('\n').findAll { it.trim() && !it.contains('File Not Found') }
                            if (fileList.size() > 0) {
                                def fileCount = fileList.size()
                                echo "[PYTHON_FOUND] ${folderName}: ${fileCount} Python files found"
                                foldersWithPython.add(folderName)

                                // Log some example files (first 3)
                                def displayFiles = fileList.take(3)
                                displayFiles.each { file ->
                                    echo "[FILE] ${file.trim()}"
                                }
                                if (fileList.size() > 3) {
                                    echo "[FILES] ... and ${fileList.size() - 3} more Python files"
                                }
                            } else {
                                echo "[NO_PYTHON] ${folderName}: No Python files found - skipping"
                            }
                        } else {
                            echo "[NO_PYTHON] ${folderName}: No Python files found - skipping"
                        }
                    }

                    echo "[PYTHON_FOLDERS] Folders with Python files: ${foldersWithPython.join(', ')}"
                    env.ALL_PYTHON_FOLDERS = foldersWithPython.join(',')

                    echo "[DETECTION] Scanning for changes in Python-containing folders..."

                    // Get list of changed files in the current commit
                    def changedFiles = []
                    try {
                        def output = bat(
                            script: '@git diff-tree --no-commit-id --name-only -r HEAD',
                            returnStdout: true
                        ).trim()

                        if (output && output != "") {
                            changedFiles = output.split('\n').findAll { it.trim() }
                        }

                        echo "[GIT_CHANGES] Found ${changedFiles.size()} changed files in commit"
                    } catch (Exception e) {
                        echo "[GIT_WARNING] Could not get git diff (possibly first commit): ${e.message}"
                        echo "[FALLBACK] Will process all folders with Python files"

                        // Fallback: treat all Python files as changed for first commit or git issues
                        foldersWithPython.each { folderName ->
                            try {
                                // Use Jenkins native approach - scan known patterns
                                if (fileExists("${folderName}")) {
                                    def foundFiles = []

                                    // Check root level Python files
                                    def rootFiles = findFiles(glob: "${folderName}/*.py")
                                    rootFiles.each { file ->
                                        foundFiles.add(file.path)
                                    }

                                    // Check subdirectories for Python files
                                    def subFiles = findFiles(glob: "${folderName}/**/*.py")
                                    subFiles.each { file ->
                                        foundFiles.add(file.path)
                                    }

                                    foundFiles.each { file ->
                                        changedFiles.add(file.replace('\\', '/'))
                                    }
                                }
                            } catch (Exception ex) {
                                echo "[WARNING] Could not scan ${folderName}: ${ex.message}"
                            }
                        }
                        echo "[FALLBACK_RESULT] Treating ${changedFiles.size()} Python files as changed"
                    }

                    // Check ALL folders for changes (not just ones with existing Python files)
                    def allFolders = allRootFolders
                    def foldersWithChanges = []
                    def folderChangeDetails = [:]

                    allFolders.each { folderName ->
                        echo "[CHECKING] Scanning ${folderName}/ for changes..."

                        // Find files changed in this folder (including all subfolders)
                        def folderChangedFiles = changedFiles.findAll { file ->
                            file.startsWith("${folderName}/")
                        }

                        if (folderChangedFiles.size() > 0) {
                            echo "[CHANGES] Found ${folderChangedFiles.size()} changed file(s) in ${folderName}/"
                            foldersWithChanges.add(folderName)

                            // Categorize changes (look for files at any depth)
                            def pythonFiles = folderChangedFiles.findAll { it.endsWith('.py') }
                            def dockerfileChanged = folderChangedFiles.any { it.endsWith('/Dockerfile') || it == "${folderName}/Dockerfile" }
                            def requirementsChanged = folderChangedFiles.any { it.endsWith('/requirements.txt') || it == "${folderName}/requirements.txt" }

                            folderChangeDetails[folderName] = [
                                python_files: pythonFiles,
                                dockerfile_changed: dockerfileChanged,
                                requirements_changed: requirementsChanged,
                                all_files: folderChangedFiles
                            ]

                            echo "[PYTHON_CHANGES] ${folderName}: ${pythonFiles.size()} Python files changed"
                            echo "[DOCKER_CONFIG] ${folderName}: Dockerfile changed: ${dockerfileChanged}"
                            echo "[REQUIREMENTS] ${folderName}: requirements.txt changed: ${requirementsChanged}"

                            // Show changed Python files (first 5)
                            def displayFiles = pythonFiles.take(5)
                            displayFiles.each { file ->
                                echo "[CHANGED_FILE] ${file}"
                            }
                            if (pythonFiles.size() > 5) {
                                echo "[MORE_FILES] ... and ${pythonFiles.size() - 5} more Python files changed"
                            }
                        } else {
                            echo "[NO_CHANGES] No changes detected in ${folderName}/"
                        }
                    }

                    // Store results for next stages
                    if (foldersWithChanges.size() > 0) {
                        env.FOLDERS_WITH_CHANGES = foldersWithChanges.join(',')
                        env.NEEDS_PROCESSING = 'true'

                        echo "[SUMMARY] Folders requiring processing:"
                        foldersWithChanges.each { folder ->
                            echo "[PROCESSING_REQUIRED] ${folder}"
                        }
                    } else {
                        echo "[INFO] No Python folders have changes requiring processing"
                        env.FOLDERS_WITH_CHANGES = ''
                        env.NEEDS_PROCESSING = 'false'
                    }

                    // Store detailed change information as JSON for later stages
                    def changeDetailsJson = new groovy.json.JsonBuilder(folderChangeDetails).toString()
                    writeFile file: 'folder_changes.json', text: changeDetailsJson

                    echo "[STORED] Change details saved for processing stages"
                }
            }
        }
        
        stage('Validate and Filter Folders') {
            when {
                environment name: 'NEEDS_PROCESSING', value: 'true'
            }
            steps {
                script {
                    echo "[VALIDATION] Validating folders with changes..."

                    def foldersToValidate = env.FOLDERS_WITH_CHANGES.split(',')
                    def validFoldersForBuild = []
                    def incompleteFolders = []

                    foldersToValidate.each { folderName ->
                        echo "[VALIDATING] Folder: ${folderName}"

                        def isValidForBuild = true
                        def validationIssues = []

                        // First, check if this folder actually contains Python files
                        def hasPythonFiles = false
                        try {
                            // Use Jenkins native approach - check for Python files
                            if (fileExists("${folderName}")) {
                                def rootFiles = findFiles(glob: "${folderName}/*.py")
                                def subFiles = findFiles(glob: "${folderName}/**/*.py")
                                hasPythonFiles = (rootFiles.size() > 0 || subFiles.size() > 0)
                            } else {
                                hasPythonFiles = false
                            }
                        } catch (Exception e) {
                            hasPythonFiles = false
                        }

                        if (!hasPythonFiles) {
                            echo "[SKIP] ${folderName}: No Python files found - skipping validation"
                            return // Skip this folder
                        }

                        echo "[PYTHON_CONFIRMED] ${folderName}: Contains Python files - proceeding with validation"

                        // Check if Dockerfile exists (at root of folder)
                        def dockerfilePath = "${folderName}/Dockerfile"
                        if (fileExists(dockerfilePath)) {
                            echo "[DOCKERFILE] Found: ${dockerfilePath}"
                        } else {
                            echo "[MISSING] Dockerfile not found: ${dockerfilePath}"
                            validationIssues.add("Missing Dockerfile")
                            isValidForBuild = false
                        }

                        // Check if requirements.txt exists (at root of folder)
                        def requirementsPath = "${folderName}/requirements.txt"
                        if (fileExists(requirementsPath)) {
                            echo "[REQUIREMENTS] Found: ${requirementsPath}"
                            def reqContent = readFile(requirementsPath)
                            def reqLines = reqContent.split('\n').findAll { it.trim() }
                            echo "[DEPENDENCIES] ${folderName} has ${reqLines.size()} dependencies"
                        } else {
                            echo "[MISSING] requirements.txt not found: ${requirementsPath}"
                            validationIssues.add("Missing requirements.txt")
                            // Note: requirements.txt is optional, don't fail build
                        }

                        // Validate Python files in the folder (recursive scan)
                        def pythonFiles = ""
                        try {
                            // Use Jenkins native approach - scan known patterns
                            if (fileExists("${folderName}")) {
                                def foundFiles = []

                                // Check root level Python files
                                def rootFiles = findFiles(glob: "${folderName}/*.py")
                                rootFiles.each { file ->
                                    foundFiles.add(file.path)
                                }

                                // Check subdirectories for Python files
                                def subFiles = findFiles(glob: "${folderName}/**/*.py")
                                subFiles.each { file ->
                                    foundFiles.add(file.path)
                                }

                                if (foundFiles.size() > 0) {
                                    pythonFiles = foundFiles.join('\n')
                                } else {
                                    pythonFiles = ""
                                }
                            } else {
                                pythonFiles = ""
                            }
                        } catch (Exception e) {
                            // No Python files found or folder doesn't exist
                            pythonFiles = ""
                        }

                        if (pythonFiles && pythonFiles != "") {
                            def fileList = pythonFiles.split('\n').findAll { it.trim() && !it.contains('File Not Found') }
                            if (fileList.size() > 0) {
                                def fileCount = 0
                                def syntaxErrors = []

                                echo "[PYTHON_VALIDATION] ${folderName}: Validating ${fileList.size()} Python files..."

                                // Validate syntax for first 5 files (to avoid overwhelming output)
                                def filesToValidate = fileList.take(5)
                                filesToValidate.each { file ->
                                    if (file.trim()) {
                                        fileCount++

                                        // Validate Python syntax (non-blocking)
                                        try {
                                            bat(script: "@python -m py_compile \"${file.trim()}\" 2>nul", returnStdout: true)
                                            echo "[SYNTAX_OK] ${file.trim().replace(env.WORKSPACE + '\\', '').replace('\\', '/')}"
                                        } catch (Exception e) {
                                            echo "[SYNTAX_ERROR] ${file.trim().replace(env.WORKSPACE + '\\', '').replace('\\', '/')}: ${e.message}"
                                            syntaxErrors.add(file.trim())
                                        }
                                    }
                                }

                                if (fileList.size() > 5) {
                                    echo "[INFO] Validated ${filesToValidate.size()} of ${fileList.size()} Python files (showing first 5)"
                                }

                                echo "[VALIDATED] ${folderName}: ${fileList.size()} Python files found across all subfolders"

                                if (syntaxErrors.size() > 0) {
                                    echo "[WARNING] ${folderName} has ${syntaxErrors.size()} files with syntax errors"
                                    validationIssues.add("Python syntax errors in ${syntaxErrors.size()} files")
                                    // Note: Syntax errors are warnings, not build blockers
                                }
                            } else {
                                echo "[WARNING] No Python files found in ${folderName}"
                                validationIssues.add("No Python files found")
                            }
                        } else {
                            echo "[WARNING] No Python files found in ${folderName}"
                            validationIssues.add("No Python files found")
                        }

                        // Categorize folder based on validation results
                        if (isValidForBuild) {
                            validFoldersForBuild.add(folderName)
                            echo "[READY_FOR_BUILD] ${folderName} - Docker build will proceed"
                        } else {
                            incompleteFolders.add(folderName)
                            echo "[INCOMPLETE] ${folderName} - Docker build will be skipped"
                            echo "[ISSUES] ${folderName}: ${validationIssues.join(', ')}"
                        }
                    }

                    // Store results for next stages
                    env.VALID_FOLDERS_FOR_BUILD = validFoldersForBuild.join(',')
                    env.INCOMPLETE_FOLDERS = incompleteFolders.join(',')

                    echo "[SUMMARY] Validation Results:"
                    echo "[BUILD_READY] ${validFoldersForBuild.size()} folders ready for Docker build: ${validFoldersForBuild.join(', ')}"
                    echo "[INCOMPLETE] ${incompleteFolders.size()} folders with missing configuration: ${incompleteFolders.join(', ')}"

                    // Update build flag based on valid folders
                    if (validFoldersForBuild.size() > 0) {
                        env.HAS_VALID_FOLDERS_FOR_BUILD = 'true'
                        echo "[PROCEED] Docker build will proceed for valid folders"
                    } else {
                        env.HAS_VALID_FOLDERS_FOR_BUILD = 'false'
                        echo "[SKIP] No folders are ready for Docker build"
                    }
                }
            }
        }
        
        stage('Build Docker Images') {
            when {
                allOf {
                    environment name: 'NEEDS_PROCESSING', value: 'true'
                    environment name: 'HAS_VALID_FOLDERS_FOR_BUILD', value: 'true'
                }
            }
            steps {
                script {
                    echo "[DOCKER] Building Docker images for validated folders..."

                    def foldersToProcess = env.VALID_FOLDERS_FOR_BUILD.split(',')
                    def buildJobs = [:]

                    if (env.INCOMPLETE_FOLDERS && env.INCOMPLETE_FOLDERS != '') {
                        echo "[SKIPPING] Folders with incomplete configuration: ${env.INCOMPLETE_FOLDERS}"
                    }

                    // Create parallel build jobs for each folder
                    foldersToProcess.each { folderName ->
                        buildJobs[folderName] = {
                            echo "[BUILD_START] Building ${folderName} Docker image..."

                            def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${folderName}"
                            def imageTag = "${env.BUILD_VERSION}-${env.COMMIT_HASH}"

                            try {
                                // Build Docker image from folder-specific Dockerfile
                                bat "docker build -t ${imageName}:${imageTag} -f ${folderName}/Dockerfile ${folderName}/"
                                bat "docker tag ${imageName}:${imageTag} ${imageName}:latest"

                                echo "[SUCCESS] ${folderName} Docker image built successfully"
                                echo "[IMAGE] ${imageName}:${imageTag}"
                                echo "[IMAGE] ${imageName}:latest"

                                // Store success status
                                writeFile file: "${folderName}_build_success.txt", text: "true"

                            } catch (Exception e) {
                                echo "[ERROR] ${folderName} Docker build failed: ${e.message}"
                                writeFile file: "${folderName}_build_success.txt", text: "false"
                                error("Docker build failed for ${folderName}")
                            }
                        }
                    }

                    // Execute builds in parallel
                    echo "[PARALLEL] Starting parallel Docker builds..."
                    parallel buildJobs

                    // Verify all builds succeeded
                    def allBuildsSuccessful = true
                    foldersToProcess.each { folderName ->
                        def buildStatus = readFile("${folderName}_build_success.txt").trim()
                        if (buildStatus != 'true') {
                            allBuildsSuccessful = false
                            echo "[FAILED] ${folderName} build was not successful"
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
                    environment name: 'NEEDS_PROCESSING', value: 'true'
                    environment name: 'HAS_VALID_FOLDERS_FOR_BUILD', value: 'true'
                    environment name: 'ALL_BUILDS_SUCCESS', value: 'true'
                }
            }
            steps {
                script {
                    echo "[ARTIFACTORY] Pushing Docker images to Artifactory..."

                    def foldersToProcess = env.VALID_FOLDERS_FOR_BUILD.split(',')
                    def pushJobs = [:]

                    // Login to Artifactory once
                    try {
                        bat """
                            docker login ${env.DOCKER_REGISTRY} -u ${env.ARTIFACTORY_CREDS_USR} -p ${env.ARTIFACTORY_CREDS_PSW}
                        """
                        echo "[LOGIN] Successfully logged into Artifactory"

                        // Create parallel push jobs for each folder
                        foldersToProcess.each { folderName ->
                            pushJobs[folderName] = {
                                echo "[PUSH_START] Pushing ${folderName} to Artifactory..."

                                def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${folderName}"
                                def imageTag = "${env.BUILD_VERSION}-${env.COMMIT_HASH}"

                                try {
                                    // Push both tagged and latest versions
                                    bat "docker push ${imageName}:${imageTag}"
                                    bat "docker push ${imageName}:latest"

                                    echo "[SUCCESS] ${folderName} images pushed successfully"
                                    echo "[PUSHED] ${imageName}:${imageTag}"
                                    echo "[PUSHED] ${imageName}:latest"

                                    // Store push success status
                                    writeFile file: "${folderName}_push_success.txt", text: "true"

                                } catch (Exception e) {
                                    echo "[ERROR] ${folderName} push failed: ${e.message}"
                                    writeFile file: "${folderName}_push_success.txt", text: "false"
                                    error("Artifactory push failed for ${folderName}")
                                }
                            }
                        }

                        // Execute pushes in parallel
                        echo "[PARALLEL] Starting parallel Artifactory pushes..."
                        parallel pushJobs

                        // Verify all pushes succeeded
                        def allPushesSuccessful = true
                        foldersToProcess.each { folderName ->
                            def pushStatus = readFile("${folderName}_push_success.txt").trim()
                            if (pushStatus != 'true') {
                                allPushesSuccessful = false
                                echo "[FAILED] ${folderName} push was not successful"
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
                    echo "[MONITORED_FOLDERS] ${env.ALL_PYTHON_FOLDERS}"

                    if (env.NEEDS_PROCESSING == 'true') {
                        echo "[FOLDERS_WITH_CHANGES] ${env.FOLDERS_WITH_CHANGES}"

                        if (env.VALID_FOLDERS_FOR_BUILD && env.VALID_FOLDERS_FOR_BUILD != '') {
                            echo "[FOLDERS_BUILT] ${env.VALID_FOLDERS_FOR_BUILD}"
                            def foldersProcessed = env.VALID_FOLDERS_FOR_BUILD.split(',')
                            foldersProcessed.each { folderName ->
                                def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${folderName}"
                                def imageTag = "${env.BUILD_VERSION}-${env.COMMIT_HASH}"

                                echo "[FOLDER] ${folderName}:"
                                echo "  [IMAGE] ${imageName}:${imageTag}"
                                echo "  [IMAGE] ${imageName}:latest"

                                // Check build status
                                try {
                                    def buildStatus = readFile("${folderName}_build_success.txt").trim()
                                    echo "  [BUILD_STATUS] ${buildStatus == 'true' ? 'SUCCESS' : 'FAILED'}"
                                } catch (Exception e) {
                                    echo "  [BUILD_STATUS] UNKNOWN"
                                }

                                // Check push status
                                try {
                                    def pushStatus = readFile("${folderName}_push_success.txt").trim()
                                    echo "  [PUSH_STATUS] ${pushStatus == 'true' ? 'SUCCESS' : 'FAILED'}"
                                } catch (Exception e) {
                                    echo "  [PUSH_STATUS] UNKNOWN"
                                }
                            }

                            if (env.ALL_BUILDS_SUCCESS == 'true') {
                                echo "[OVERALL_BUILD] SUCCESS - All valid folders built successfully"
                            } else {
                                echo "[OVERALL_BUILD] FAILED - Some folders failed to build"
                            }

                            if (env.ALL_PUSHES_SUCCESS == 'true') {
                                echo "[OVERALL_PUSH] SUCCESS - All images pushed to Artifactory"
                            } else {
                                echo "[OVERALL_PUSH] FAILED - Some images failed to push"
                            }
                        } else {
                            echo "[NO_VALID_FOLDERS] No folders were ready for Docker build"
                        }

                        // Report incomplete folders
                        if (env.INCOMPLETE_FOLDERS && env.INCOMPLETE_FOLDERS != '') {
                            echo "[INCOMPLETE_FOLDERS] ${env.INCOMPLETE_FOLDERS}"
                            def incompleteFolders = env.INCOMPLETE_FOLDERS.split(',')
                            incompleteFolders.each { folderName ->
                                echo "[SKIPPED] ${folderName} - Missing Docker configuration"
                            }
                            echo "[INFO] Add Dockerfile to incomplete folders to enable Docker builds"
                        }
                    } else {
                        echo "[FOLDER_CHANGES] NO - No Python folders have changes"
                        echo "[INFO] This commit doesn't affect any folders containing Python files"
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
