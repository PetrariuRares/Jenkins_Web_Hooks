pipeline {
    agent any

    triggers {
        // GitHub webhook trigger for main branch
        githubPush()
        // Backup: Poll SCM every 5 minutes (optional, remove if webhook works)
        pollSCM('H/5 * * * *')
    }

    environment {
        // Application configuration
        PYTHON_VERSION = '3.11'

        // Docker configuration
        DOCKER_REGISTRY = 'trialqlk1tc.jfrog.io'
        DOCKER_REPO = 'dockertest-docker'

        // Artifactory credentials
        ARTIFACTORY_CREDS = credentials('artifactory-credentials')

        // Build configuration
        BUILD_VERSION = "${BUILD_NUMBER}"
        COMMIT_HASH = "${GIT_COMMIT ? GIT_COMMIT.take(8) : 'unknown'}"
    }

    stages {
        stage('Checkout') {
            steps {
                echo "[CHECKOUT] Checking out repository..."
                checkout scm

                script {
                    // Get branch name
                    env.GIT_BRANCH_NAME = env.GIT_BRANCH ? env.GIT_BRANCH.replaceAll('.*/', '') : 'unknown'
                    echo "[BRANCH] Building from branch: ${env.GIT_BRANCH_NAME}"

                    // Only proceed if on main branch
                    if (env.GIT_BRANCH_NAME != 'main' && env.GIT_BRANCH_NAME != 'master') {
                        echo "[SKIP] Not on main/master branch. Current branch: ${env.GIT_BRANCH_NAME}"
                        env.SKIP_BUILD = 'true'
                    } else {
                        env.SKIP_BUILD = 'false'
                    }

                    try {
                        // Try Unix-style commands first (for Linux agents)
                        env.GIT_COMMIT_MSG = sh(
                            script: 'git log -1 --pretty=%B',
                            returnStdout: true
                        ).trim()
                        env.GIT_AUTHOR = sh(
                            script: 'git log -1 --pretty=%an',
                            returnStdout: true
                        ).trim()
                        env.GIT_COMMIT_HASH = sh(
                            script: 'git rev-parse HEAD',
                            returnStdout: true
                        ).trim()
                    } catch (Exception e) {
                        // Fallback to Windows commands
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
                        } catch (Exception e2) {
                            echo "[WARNING] Could not retrieve git information"
                            env.GIT_COMMIT_MSG = "Unknown"
                            env.GIT_AUTHOR = "Unknown"
                            env.GIT_COMMIT_HASH = "unknown-${BUILD_NUMBER}"
                        }
                    }

                    echo "[COMMIT] ${env.GIT_COMMIT_HASH}"
                    echo "[AUTHOR] ${env.GIT_AUTHOR}"
                    echo "[MESSAGE] ${env.GIT_COMMIT_MSG}"
                }
            }
        }

        stage('Detect Python Changes') {
            when {
                environment name: 'SKIP_BUILD', value: 'false'
            }
            steps {
                script {
                    echo "[DISCOVERY] Scanning repository for Python files and changes..."

                    def isWindows = isUnix() ? false : true
                    def pythonFolders = []
                    def changedFolders = []

                    // Find all folders containing Python files
                    if (isWindows) {
                        // Windows commands
                        def allFiles = bat(
                            script: '@dir /s /b *.py 2>nul',
                            returnStdout: true
                        ).trim()

                        if (allFiles) {
                            def files = allFiles.split('\r?\n')
                            files.each { file ->
                                // Extract folder name from path
                                def relativePath = file.replace(env.WORKSPACE + '\\', '').replace('\\', '/')
                                def parts = relativePath.split('/')
                                if (parts.length > 1) {
                                    def folder = parts[0]
                                    if (!pythonFolders.contains(folder) && !folder.startsWith('.')) {
                                        pythonFolders.add(folder)
                                    }
                                }
                            }
                        }
                    } else {
                        // Unix/Linux commands
                        def findResult = sh(
                            script: 'find . -name "*.py" -type f 2>/dev/null | head -1000',
                            returnStdout: true
                        ).trim()

                        if (findResult) {
                            def files = findResult.split('\n')
                            files.each { file ->
                                // Remove ./ prefix and extract folder
                                def path = file.replaceFirst('^\\./', '')
                                def parts = path.split('/')
                                if (parts.length > 1) {
                                    def folder = parts[0]
                                    if (!pythonFolders.contains(folder) && !folder.startsWith('.')) {
                                        pythonFolders.add(folder)
                                    }
                                }
                            }
                        }
                    }

                    echo "[PYTHON_FOLDERS] Found ${pythonFolders.size()} folders with Python files: ${pythonFolders.join(', ')}"

                    // Detect changed files
                    def changedFiles = []
                    try {
                        // Check if this is the first commit
                        def commitCount = isWindows ? 
                            bat(script: '@git rev-list --count HEAD', returnStdout: true).trim() :
                            sh(script: 'git rev-list --count HEAD', returnStdout: true).trim()

                        if (commitCount == '1') {
                            echo "[FIRST_COMMIT] This is the first commit - treating all Python files as changed"
                            // For first commit, treat all Python folders as changed
                            changedFolders = pythonFolders
                        } else {
                            // Get list of changed files
                            def gitDiff = isWindows ?
                                bat(script: '@git diff --name-only HEAD~1 HEAD', returnStdout: true).trim() :
                                sh(script: 'git diff --name-only HEAD~1 HEAD', returnStdout: true).trim()

                            if (gitDiff) {
                                changedFiles = gitDiff.split('\r?\n')
                                echo "[CHANGED_FILES] Found ${changedFiles.size()} changed files:"
                                
                                // List all changed files
                                changedFiles.each { file ->
                                    echo "  - ${file}"
                                }

                                // Group changes by folder
                                def changesByFolder = [:]
                                changedFiles.each { file ->
                                    def parts = file.split('/')
                                    if (parts.length > 0) {
                                        def folder = parts[0]
                                        if (!changesByFolder[folder]) {
                                            changesByFolder[folder] = []
                                        }
                                        changesByFolder[folder].add(file)
                                        
                                        if (pythonFolders.contains(folder) && !changedFolders.contains(folder)) {
                                            changedFolders.add(folder)
                                        }
                                    }
                                }
                                
                                // Display changes grouped by folder
                                echo "\n[CHANGES_BY_FOLDER]:"
                                changesByFolder.each { folder, files ->
                                    echo "  ${folder}/ (${files.size()} files):"
                                    files.each { file ->
                                        def fileType = file.endsWith('.py') ? '[Python]' : 
                                                      file.endsWith('Dockerfile') ? '[Docker]' :
                                                      file.endsWith('requirements.txt') ? '[Requirements]' : '[Other]'
                                        echo "    ${fileType} ${file}"
                                    }
                                }
                            }
                        }
                    } catch (Exception e) {
                        echo "[WARNING] Could not determine changes, will process all Python folders"
                        changedFolders = pythonFolders
                    }

                    echo "[CHANGED_FOLDERS] Folders with changes: ${changedFolders.join(', ')}"

                    // Set environment variables for next stages
                    if (changedFolders.size() > 0) {
                        env.FOLDERS_WITH_CHANGES = changedFolders.join(',')
                        env.NEEDS_PROCESSING = 'true'
                    } else {
                        echo "[INFO] No Python folders have changes"
                        env.FOLDERS_WITH_CHANGES = ''
                        env.NEEDS_PROCESSING = 'false'
                    }
                }
            }
        }

        stage('Validate Folders') {
            when {
                allOf {
                    environment name: 'SKIP_BUILD', value: 'false'
                    environment name: 'NEEDS_PROCESSING', value: 'true'
                }
            }
            steps {
                script {
                    echo "[VALIDATION] Validating folders with changes..."

                    def foldersToValidate = env.FOLDERS_WITH_CHANGES.split(',')
                    def validFolders = []
                    def invalidFolders = []

                    foldersToValidate.each { folder ->
                        echo "[CHECKING] ${folder}/"

                        def hasDockerfile = fileExists("${folder}/Dockerfile")
                        def hasRequirements = fileExists("${folder}/requirements.txt")

                        if (hasDockerfile) {
                            echo "[✓] ${folder}/Dockerfile exists"
                            validFolders.add(folder)

                            if (!hasRequirements) {
                                echo "[WARNING] ${folder}/requirements.txt not found (will use empty requirements)"
                                // Create empty requirements.txt if it doesn't exist
                                writeFile file: "${folder}/requirements.txt", text: "# No dependencies\n"
                            }
                        } else {
                            echo "[✗] ${folder}/Dockerfile missing - skipping Docker build"
                            invalidFolders.add(folder)
                        }
                    }

                    env.VALID_FOLDERS = validFolders.join(',')
                    env.INVALID_FOLDERS = invalidFolders.join(',')

                    if (validFolders.size() > 0) {
                        env.HAS_VALID_FOLDERS = 'true'
                        echo "[SUMMARY] ${validFolders.size()} folders ready for Docker build"
                    } else {
                        env.HAS_VALID_FOLDERS = 'false'
                        echo "[SUMMARY] No folders are ready for Docker build"
                    }
                }
            }
        }

        stage('Build Docker Images') {
            when {
                allOf {
                    environment name: 'SKIP_BUILD', value: 'false'
                    environment name: 'HAS_VALID_FOLDERS', value: 'true'
                }
            }
            steps {
                script {
                    echo "[DOCKER] Building Docker images..."

                    def folders = env.VALID_FOLDERS.split(',')
                    def buildJobs = [:]

                    folders.each { folder ->
                        buildJobs[folder] = {
                            echo "[BUILD] Building ${folder}..."

                            def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${folder}"
                            def imageTag = "${env.BUILD_VERSION}-${env.COMMIT_HASH}"

                            try {
                                // Build Docker image
                                def isWindows = isUnix() ? false : true
                                if (isWindows) {
                                    bat "docker build -t ${imageName}:${imageTag} -f ${folder}/Dockerfile ${folder}/"
                                    bat "docker tag ${imageName}:${imageTag} ${imageName}:latest"
                                } else {
                                    sh "docker build -t ${imageName}:${imageTag} -f ${folder}/Dockerfile ${folder}/"
                                    sh "docker tag ${imageName}:${imageTag} ${imageName}:latest"
                                }

                                echo "[SUCCESS] ${folder} image built: ${imageName}:${imageTag}"
                                writeFile file: "${folder}_build_success.txt", text: "true"

                            } catch (Exception e) {
                                echo "[ERROR] Failed to build ${folder}: ${e.message}"
                                writeFile file: "${folder}_build_success.txt", text: "false"
                                throw e
                            }
                        }
                    }

                    // Execute builds in parallel
                    parallel buildJobs

                    env.BUILD_COMPLETE = 'true'
                }
            }
        }

        stage('Push to Artifactory') {
            when {
                allOf {
                    environment name: 'SKIP_BUILD', value: 'false'
                    environment name: 'BUILD_COMPLETE', value: 'true'
                }
            }
            steps {
                script {
                    echo "[PUSH] Pushing images to Artifactory..."

                    def folders = env.VALID_FOLDERS.split(',')
                    def isWindows = isUnix() ? false : true

                    // Login to Artifactory using secure credential handling
                    withCredentials([usernamePassword(
                        credentialsId: 'artifactory-credentials',
                        usernameVariable: 'ARTIFACTORY_USER',
                        passwordVariable: 'ARTIFACTORY_PASS'
                    )]) {
                        // Use password-stdin for security
                        if (isWindows) {
                            bat '''
                                echo %ARTIFACTORY_PASS% | docker login %DOCKER_REGISTRY% -u %ARTIFACTORY_USER% --password-stdin
                            '''
                        } else {
                            sh '''
                                echo $ARTIFACTORY_PASS | docker login $DOCKER_REGISTRY -u $ARTIFACTORY_USER --password-stdin
                            '''
                        }
                        
                        echo "[LOGIN] Successfully logged into Artifactory"

                        def pushJobs = [:]

                        folders.each { folder ->
                            pushJobs[folder] = {
                                def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${folder}"
                                def imageTag = "${env.BUILD_VERSION}-${env.COMMIT_HASH}"

                                try {
                                    if (isWindows) {
                                        bat "docker push ${imageName}:${imageTag}"
                                        bat "docker push ${imageName}:latest"
                                    } else {
                                        sh "docker push ${imageName}:${imageTag}"
                                        sh "docker push ${imageName}:latest"
                                    }

                                    echo "[SUCCESS] Pushed ${imageName}:${imageTag} and ${imageName}:latest"

                                } catch (Exception e) {
                                    echo "[ERROR] Failed to push ${folder}: ${e.message}"
                                    throw e
                                }
                            }
                        }

                        // Execute pushes in parallel
                        parallel pushJobs
                    }

                    // Logout
                    if (isWindows) {
                        bat "docker logout ${env.DOCKER_REGISTRY}"
                    } else {
                        sh "docker logout ${env.DOCKER_REGISTRY}"
                    }
                }
            }
        }

        stage('Summary') {
            steps {
                script {
                    echo "\n========================================="
                    echo "BUILD SUMMARY"
                    echo "========================================="
                    echo "Branch: ${env.GIT_BRANCH_NAME ?: 'unknown'}"
                    echo "Commit: ${env.GIT_COMMIT_HASH}"
                    echo "Author: ${env.GIT_AUTHOR}"
                    echo "Build #: ${env.BUILD_NUMBER}"

                    if (env.SKIP_BUILD == 'true') {
                        echo "Status: SKIPPED (not on main branch)"
                    } else if (env.NEEDS_PROCESSING == 'true') {
                        echo "Folders with changes: ${env.FOLDERS_WITH_CHANGES}"
                        if (env.HAS_VALID_FOLDERS == 'true') {
                            echo "Docker images built: ${env.VALID_FOLDERS}"
                            def folders = env.VALID_FOLDERS.split(',')
                            folders.each { folder ->
                                echo "  - ${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${folder}:${env.BUILD_VERSION}-${env.COMMIT_HASH}"
                            }
                        }
                        if (env.INVALID_FOLDERS && env.INVALID_FOLDERS != '') {
                            echo "Skipped (missing Dockerfile): ${env.INVALID_FOLDERS}"
                        }
                    } else {
                        echo "Status: No Python changes detected"
                    }
                    echo "========================================="
                }
            }
        }
    }

    post {
        always {
            echo "[CLEANUP] Pipeline completed"
        }
        success {
            echo "[SUCCESS] Pipeline executed successfully!"
        }
        failure {
            echo "[FAILURE] Pipeline failed!"
            // Optionally send notifications
        }
    }
}