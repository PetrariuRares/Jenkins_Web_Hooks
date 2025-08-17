pipeline {
    agent any

    parameters {
        // Manual trigger parameters for flexible pipeline execution
        string(
            name: 'BRANCH_NAME',
            defaultValue: '',
            description: 'Branch to build (leave empty for automatic detection from webhook)'
        )
        choice(
            name: 'DEPLOY_TARGET',
            choices: ['auto', 'latest', 'dev'],
            description: 'Where to deploy (auto = based on branch, latest = production, dev = development)'
        )
        booleanParam(
            name: 'FORCE_BUILD',
            defaultValue: false,
            description: 'Force build all applications even if no changes detected'
        )
    }

    triggers {
        // GitHub webhook trigger for automatic builds on push
        githubPush()
    }

    environment {
        // Docker registry configuration
        DOCKER_REGISTRY = 'trialqlk1tc.jfrog.io'
        DOCKER_REPO = 'dockertest-docker'

        // Artifactory credentials from Jenkins credentials store
        ARTIFACTORY_CREDS = credentials('artifactory-credentials')

        // Build metadata
        BUILD_NUMBER = "${BUILD_NUMBER}"
        TIMESTAMP = "${new Date().format('yyyyMMdd-HHmmss')}"
        
        // Pipeline status flags
        NO_APPS = 'false'
        
        // ANSI color codes for better console output visibility
        COLOR_RESET = '\033[0m'
        COLOR_RED = '\033[0;31m'
        COLOR_GREEN = '\033[0;32m'
        COLOR_YELLOW = '\033[1;33m'
        COLOR_BLUE = '\033[0;34m'
        COLOR_CYAN = '\033[0;36m'
        COLOR_MAGENTA = '\033[0;35m'
    }

    stages {
        // ================================================================================
        // STAGE 1: Initialize Pipeline
        // Sets up the build environment and displays configuration
        // ================================================================================
        stage('Initialize') {
            steps {
                script {
                    echo "${COLOR_CYAN}=========================================${COLOR_RESET}"
                    echo "${COLOR_CYAN}BUILD INITIALIZATION${COLOR_RESET}"
                    echo "${COLOR_CYAN}=========================================${COLOR_RESET}"
                    echo "${COLOR_GREEN}Build Number: ${BUILD_NUMBER}${COLOR_RESET}"
                    echo "${COLOR_GREEN}Manual Branch Override: ${params.BRANCH_NAME ?: 'none'}${COLOR_RESET}"
                    echo "${COLOR_GREEN}Deploy Target: ${params.DEPLOY_TARGET}${COLOR_RESET}"
                    echo "${COLOR_GREEN}Force Build: ${params.FORCE_BUILD}${COLOR_RESET}"
                    echo "${COLOR_CYAN}=========================================${COLOR_RESET}"
                }
            }
        }

        // ================================================================================
        // STAGE 2: Checkout Code
        // Handles both manual branch selection and webhook triggers
        // Determines deployment target based on branch name
        // ================================================================================
        stage('Checkout') {
            steps {
                script {
                    // Clean workspace before checkout to ensure fresh state
                    echo "${COLOR_YELLOW}[WORKSPACE] Cleaning previous workspace...${COLOR_RESET}"
                    deleteDir()
                    
                    // Handle manual branch override vs webhook trigger
                    if (params.BRANCH_NAME) {
                        echo "${COLOR_BLUE}[CHECKOUT] Checking out specified branch: ${params.BRANCH_NAME}${COLOR_RESET}"
                        checkout([
                            $class: 'GitSCM',
                            branches: [[name: "*/${params.BRANCH_NAME}"]],
                            extensions: [],
                            userRemoteConfigs: scm.userRemoteConfigs
                        ])
                        env.GIT_BRANCH_NAME = params.BRANCH_NAME
                    } else {
                        echo "${COLOR_BLUE}[CHECKOUT] Checking out from webhook trigger...${COLOR_RESET}"
                        checkout scm
                        
                        // Determine current branch name from git
                        try {
                            env.GIT_BRANCH_NAME = bat(
                                script: '@git rev-parse --abbrev-ref HEAD',
                                returnStdout: true
                            ).trim()
                            
                            // Handle detached HEAD state
                            if (env.GIT_BRANCH_NAME == 'HEAD') {
                                env.GIT_BRANCH_NAME = bat(
                                    script: '@git branch -r --contains HEAD',
                                    returnStdout: true
                                ).trim()
                                // Clean up the branch name
                                env.GIT_BRANCH_NAME = env.GIT_BRANCH_NAME.replaceAll('.*origin/', '').trim()
                            }
                        } catch (Exception e) {
                            env.GIT_BRANCH_NAME = 'unknown'
                        }
                    }

                    // Clean branch name format (remove origin/ prefix if present)
                    if (env.GIT_BRANCH_NAME.contains('/')) {
                        def parts = env.GIT_BRANCH_NAME.split('/')
                        if (parts[0] == 'origin') {
                            env.GIT_BRANCH_NAME = parts[1..-1].join('/')
                        }
                    }

                    // Extract commit information for traceability
                    try {
                        env.GIT_COMMIT_HASH = bat(
                            script: '@git rev-parse --short=8 HEAD',
                            returnStdout: true
                        ).trim()
                        env.GIT_COMMIT_MSG = bat(
                            script: '@git log -1 --pretty=%%B',
                            returnStdout: true
                        ).trim()
                        env.GIT_AUTHOR = bat(
                            script: '@git log -1 --pretty=%%an',
                            returnStdout: true
                        ).trim()
                    } catch (Exception e) {
                        env.GIT_COMMIT_HASH = "unknown-${BUILD_NUMBER}"
                        env.GIT_COMMIT_MSG = "Unknown"
                        env.GIT_AUTHOR = "Unknown"
                    }

                    echo "${COLOR_GREEN}[BRANCH] ${env.GIT_BRANCH_NAME}${COLOR_RESET}"
                    echo "${COLOR_GREEN}[COMMIT] ${env.GIT_COMMIT_HASH}${COLOR_RESET}"
                    echo "${COLOR_GREEN}[AUTHOR] ${env.GIT_AUTHOR}${COLOR_RESET}"
                    echo "${COLOR_GREEN}[MESSAGE] ${env.GIT_COMMIT_MSG}${COLOR_RESET}"

                    // Determine deployment environment based on branch or manual override
                    if (params.DEPLOY_TARGET != 'auto') {
                        // Manual deployment target override
                        env.DEPLOY_ENV = params.DEPLOY_TARGET
                        echo "${COLOR_MAGENTA}[DEPLOY] Manual override: deploying to '${env.DEPLOY_ENV}'${COLOR_RESET}"
                    } else {
                        // Auto-determine based on branch naming convention
                        if (env.GIT_BRANCH_NAME == 'main' || env.GIT_BRANCH_NAME == 'master') {
                            env.DEPLOY_ENV = 'latest'
                            echo "${COLOR_MAGENTA}[DEPLOY] Main branch detected: deploying to 'latest'${COLOR_RESET}"
                        } else {
                            env.DEPLOY_ENV = 'dev'
                            echo "${COLOR_MAGENTA}[DEPLOY] Feature branch detected: deploying to 'dev' with branch tag${COLOR_RESET}"
                        }
                    }
                }
            }
        }

        // ================================================================================
        // STAGE 3: Detect Changes
        // Scans for applications with Dockerfiles
        // Calculates content hashes to determine what needs rebuilding
        // Compares with existing images in Artifactory
        // ================================================================================
        stage('Detect Changes') {
            steps {
                script {
                    echo "${COLOR_CYAN}[DISCOVERY] Scanning for Python applications...${COLOR_RESET}"

                    def pythonApps = []
                    def changedApps = []

                    // Find all Dockerfiles in the repository
                    def dockerfiles = ''
                    try {
                        dockerfiles = bat(
                            script: '@dir /s /b Dockerfile 2>nul || exit 0',
                            returnStdout: true
                        ).trim()
                    } catch (Exception e) {
                        echo "${COLOR_YELLOW}[INFO] No Dockerfiles found in repository${COLOR_RESET}"
                        dockerfiles = ''
                    }

                    // Process found Dockerfiles to identify applications
                    if (dockerfiles) {
                        dockerfiles.split('\r?\n').each { file ->
                            if (file && file.trim()) {
                                def relativePath = file.replace(env.WORKSPACE + '\\', '').replace('\\', '/')
                                def parts = relativePath.split('/')
                                // Only consider Dockerfiles in immediate subdirectories (app pattern)
                                if (parts.length == 2 && parts[1] == 'Dockerfile') {
                                    def appName = parts[0]
                                    // Skip hidden directories
                                    if (!appName.startsWith('.')) {
                                        pythonApps.add(appName)
                                    }
                                }
                            }
                        }
                    }

                    echo "${COLOR_GREEN}[APPS] Found ${pythonApps.size()} applications: ${pythonApps.join(', ')}${COLOR_RESET}"

                    // Exit early if no applications found
                    if (pythonApps.size() == 0) {
                        env.HAS_CHANGES = 'false'
                        env.NO_APPS = 'true'
                        echo "${COLOR_YELLOW}[INFO] No applications with Dockerfiles found in repository${COLOR_RESET}"
                        echo "${COLOR_YELLOW}[INFO] Pipeline will complete without building any images${COLOR_RESET}"
                        return
                    }

                    // Calculate content hash for each application
                    // This hash represents the current state of the application's code
                    def appHashes = [:]
                    pythonApps.each { app ->
                        def hash = calculateAppContentHash(app)
                        appHashes[app] = hash
                        echo "${COLOR_BLUE}[HASH] ${app}: ${hash}${COLOR_RESET}"
                    }

                    // Connect to Artifactory to check existing images
                    withCredentials([usernamePassword(
                        credentialsId: 'artifactory-credentials',
                        usernameVariable: 'ARTIFACTORY_USER',
                        passwordVariable: 'ARTIFACTORY_PASS'
                    )]) {
                        bat 'echo %ARTIFACTORY_PASS% | docker login %DOCKER_REGISTRY% -u %ARTIFACTORY_USER% --password-stdin'

                        // Check each application to determine if rebuild is needed
                        pythonApps.each { app ->
                            def currentHash = appHashes[app]
                            def needsBuild = false

                            // Determine the Docker tag based on environment
                            def imageTag = ''
                            if (env.DEPLOY_ENV == 'latest') {
                                imageTag = 'latest'
                            } else {
                                // For dev environment, use sanitized branch name as tag
                                def cleanBranchName = env.GIT_BRANCH_NAME
                                    .replaceAll('[^a-zA-Z0-9._-]', '-')
                                    .toLowerCase()
                                imageTag = cleanBranchName
                            }

                            def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${app}:${imageTag}"

                            // Check if image exists in registry and compare content hash
                            try {
                                // Attempt to pull the image from registry
                                def pullResult = bat(
                                    script: "docker pull ${imageName} 2>&1",
                                    returnStatus: true
                                )

                                if (pullResult == 0) {
                                    // Image exists, extract and compare content hash from labels
                                    def existingHash = bat(
                                        script: "@docker inspect ${imageName} --format=\"{{index .Config.Labels \\\"content.hash\\\"}}\" 2>nul || echo \"\"",
                                        returnStdout: true
                                    ).trim()

                                    if (existingHash && existingHash != currentHash) {
                                        echo "${COLOR_YELLOW}[CHANGE] ${app}: Content changed (${existingHash} -> ${currentHash})${COLOR_RESET}"
                                        needsBuild = true
                                    } else if (!existingHash) {
                                        echo "${COLOR_YELLOW}[CHANGE] ${app}: No content hash in existing image, rebuilding${COLOR_RESET}"
                                        needsBuild = true
                                    } else {
                                        echo "${COLOR_GREEN}[SKIP] ${app}: Content unchanged (${currentHash})${COLOR_RESET}"
                                    }
                                    
                                    // Clean up pulled image to save space
                                    bat "docker rmi ${imageName} 2>nul || exit 0"
                                } else {
                                    echo "${COLOR_YELLOW}[NEW] ${app}: Image doesn't exist in registry${COLOR_RESET}"
                                    needsBuild = true
                                }
                            } catch (Exception e) {
                                echo "${COLOR_YELLOW}[NEW] ${app}: Unable to check existing image, will build${COLOR_RESET}"
                                needsBuild = true
                            }

                            // Add to build list if changes detected or force build enabled
                            if (needsBuild || params.FORCE_BUILD) {
                                changedApps.add(app)
                                // Store hash for build stage
                                writeFile file: "${app}_hash.txt", text: currentHash
                            }
                        }

                        bat "docker logout ${env.DOCKER_REGISTRY}"
                    }

                    // Set environment variables based on detection results
                    if (changedApps.size() > 0) {
                        env.APPS_TO_BUILD = changedApps.join(',')
                        env.HAS_CHANGES = 'true'
                        echo "${COLOR_GREEN}[BUILD_LIST] Applications to build: ${env.APPS_TO_BUILD}${COLOR_RESET}"
                    } else {
                        env.HAS_CHANGES = 'false'
                        echo "${COLOR_GREEN}[INFO] No applications need building - all content is up to date${COLOR_RESET}"
                    }
                }
            }
        }

        // ================================================================================
        // STAGE 4: Build Docker Images
        // Builds only the applications that have changes
        // Uses parallel execution for efficiency
        // Adds content hash as Docker label for future comparison
        // ================================================================================
        stage('Build Docker Images') {
            when {
                environment name: 'HAS_CHANGES', value: 'true'
            }
            steps {
                script {
                    echo "${COLOR_CYAN}[DOCKER] Building Docker images...${COLOR_RESET}"

                    def apps = env.APPS_TO_BUILD.split(',')
                    def buildJobs = [:]

                    // Create parallel build jobs for each application
                    apps.each { app ->
                        buildJobs[app] = {
                            echo "${COLOR_BLUE}[BUILD] Building ${app}...${COLOR_RESET}"

                            // Read the content hash calculated earlier
                            def contentHash = readFile("${app}_hash.txt").trim()

                            // Determine the tag based on deployment environment
                            def imageTag = ''
                            if (env.DEPLOY_ENV == 'latest') {
                                imageTag = 'latest'
                            } else {
                                def cleanBranchName = env.GIT_BRANCH_NAME
                                    .replaceAll('[^a-zA-Z0-9._-]', '-')
                                    .toLowerCase()
                                imageTag = cleanBranchName
                            }

                            def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${app}"

                            try {
                                // Ensure requirements.txt exists (some apps might not have dependencies)
                                if (!fileExists("${app}/requirements.txt")) {
                                    writeFile file: "${app}/requirements.txt", text: "# No dependencies\n"
                                }

                                // Build Docker image with metadata labels
                                // Labels are used to track content hash and build information
                                bat """
                                    docker build \
                                        -t ${imageName}:${imageTag} \
                                        --label content.hash=${contentHash} \
                                        --label build.number=${BUILD_NUMBER} \
                                        --label git.commit=${env.GIT_COMMIT_HASH} \
                                        --label git.branch=${env.GIT_BRANCH_NAME} \
                                        --label build.timestamp=${env.TIMESTAMP} \
                                        -f ${app}/Dockerfile ${app}/
                                """
                                
                                echo "${COLOR_GREEN}[SUCCESS] Built ${imageName}:${imageTag} with hash ${contentHash}${COLOR_RESET}"
                                
                                // Store tag for push stage
                                writeFile file: "${app}_tag.txt", text: imageTag

                            } catch (Exception e) {
                                echo "${COLOR_RED}[ERROR] Failed to build ${app}: ${e.message}${COLOR_RESET}"
                                throw e
                            }
                        }
                    }

                    // Execute all build jobs in parallel
                    parallel buildJobs
                    env.BUILD_COMPLETE = 'true'
                }
            }
        }

        // ================================================================================
        // STAGE 5: Push to Artifactory
        // Pushes built images to JFrog Artifactory
        // Uses parallel uploads for efficiency
        // ================================================================================
        stage('Push to Artifactory') {
            when {
                environment name: 'BUILD_COMPLETE', value: 'true'
            }
            steps {
                script {
                    echo "${COLOR_CYAN}[PUSH] Pushing images to Artifactory...${COLOR_RESET}"

                    def apps = env.APPS_TO_BUILD.split(',')

                    // Authenticate with Artifactory
                    withCredentials([usernamePassword(
                        credentialsId: 'artifactory-credentials',
                        usernameVariable: 'ARTIFACTORY_USER',
                        passwordVariable: 'ARTIFACTORY_PASS'
                    )]) {
                        bat 'echo %ARTIFACTORY_PASS% | docker login %DOCKER_REGISTRY% -u %ARTIFACTORY_USER% --password-stdin'
                        
                        echo "${COLOR_GREEN}[LOGIN] Successfully logged into Artifactory${COLOR_RESET}"

                        def pushJobs = [:]

                        // Create parallel push jobs for each application
                        apps.each { app ->
                            pushJobs[app] = {
                                def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${app}"
                                def imageTag = readFile("${app}_tag.txt").trim()
                                
                                try {
                                    // Push image to registry
                                    bat "docker push ${imageName}:${imageTag}"
                                    echo "${COLOR_GREEN}[PUSHED] ${imageName}:${imageTag}${COLOR_RESET}"
                                    
                                    // Store pushed tag for summary report
                                    env."${app}_PUSHED_TAG" = imageTag
                                    
                                } catch (Exception e) {
                                    echo "${COLOR_RED}[ERROR] Failed to push ${imageName}:${imageTag}: ${e.message}${COLOR_RESET}"
                                    throw e
                                }
                            }
                        }

                        // Execute all push jobs in parallel
                        parallel pushJobs
                    }

                    // Logout from registry
                    bat "docker logout ${env.DOCKER_REGISTRY}"
                }
            }
        }

        // ================================================================================
        // STAGE 6: Cleanup Temporary Files
        // Removes temporary files created during the build process
        // ================================================================================
        stage('Cleanup Temp Files') {
            when {
                environment name: 'BUILD_COMPLETE', value: 'true'
            }
            steps {
                script {
                    echo "${COLOR_YELLOW}[CLEANUP] Cleaning up temporary files...${COLOR_RESET}"
                    
                    try {
                        // Remove temporary tag and hash files
                        bat 'del /Q *_tag.txt 2>nul || exit 0'
                        bat 'del /Q *_hash.txt 2>nul || exit 0'
                        
                        echo "${COLOR_GREEN}[CLEANUP] Temporary files removed${COLOR_RESET}"
                    } catch (Exception e) {
                        echo "${COLOR_YELLOW}[WARNING] Temp file cleanup failed: ${e.message}${COLOR_RESET}"
                    }
                }
            }
        }

        // ================================================================================
        // STAGE 7: Build Summary
        // Displays comprehensive build results and instructions
        // ================================================================================
        stage('Summary') {
            steps {
                script {
                    echo "\n${COLOR_CYAN}=========================================${COLOR_RESET}"
                    echo "${COLOR_CYAN}BUILD SUMMARY${COLOR_RESET}"
                    echo "${COLOR_CYAN}=========================================${COLOR_RESET}"
                    echo "${COLOR_GREEN}Branch: ${env.GIT_BRANCH_NAME}${COLOR_RESET}"
                    echo "${COLOR_GREEN}Commit: ${env.GIT_COMMIT_HASH}${COLOR_RESET}"
                    echo "${COLOR_GREEN}Author: ${env.GIT_AUTHOR}${COLOR_RESET}"
                    echo "${COLOR_GREEN}Build #: ${env.BUILD_NUMBER}${COLOR_RESET}"
                    echo "${COLOR_GREEN}Target: ${env.DEPLOY_ENV}${COLOR_RESET}"
                    
                    if (params.BRANCH_NAME) {
                        echo "${COLOR_YELLOW}Manual Branch Override: ${params.BRANCH_NAME}${COLOR_RESET}"
                    }

                    // Display appropriate summary based on build results
                    if (env.NO_APPS == 'true') {
                        echo "\n${COLOR_YELLOW}Status: No applications with Dockerfiles found in repository${COLOR_RESET}"
                        echo "${COLOR_YELLOW}Add applications with Dockerfiles to enable Docker builds${COLOR_RESET}"
                    } else if (env.HAS_CHANGES == 'true') {
                        echo "\n${COLOR_GREEN}Applications Built and Pushed:${COLOR_RESET}"
                        def apps = env.APPS_TO_BUILD.split(',')
                        apps.each { app ->
                            def pushedTag = env."${app}_PUSHED_TAG"
                            echo "  ${COLOR_BLUE}${app}:${COLOR_RESET}"
                            echo "    ${COLOR_GREEN}Image: ${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${app}:${pushedTag}${COLOR_RESET}"
                            echo "    ${COLOR_GREEN}Registry URL: https://${env.DOCKER_REGISTRY}/artifactory/webapp/#/artifacts/browse/tree/General/${env.DOCKER_REPO}/${app}${COLOR_RESET}"
                        }
                        
                        // Provide docker pull commands for easy access
                        echo "\n${COLOR_CYAN}To pull images:${COLOR_RESET}"
                        apps.each { app ->
                            def pushedTag = env."${app}_PUSHED_TAG"
                            echo "  ${COLOR_YELLOW}docker pull ${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${app}:${pushedTag}${COLOR_RESET}"
                        }
                    } else {
                        echo "\n${COLOR_GREEN}Status: No changes detected - all applications are up to date${COLOR_RESET}"
                    }
                    
                    echo "${COLOR_CYAN}=========================================${COLOR_RESET}"

                    // Update Jenkins build description for dashboard visibility
                    if (env.NO_APPS == 'true') {
                        currentBuild.description = "No apps found | ${env.GIT_BRANCH_NAME}"
                    } else if (env.HAS_CHANGES == 'true') {
                        currentBuild.description = "${env.DEPLOY_ENV} | ${env.GIT_BRANCH_NAME} | ${env.APPS_TO_BUILD}"
                    } else {
                        currentBuild.description = "No changes | ${env.GIT_BRANCH_NAME}"
                    }
                }
            }
        }
    }

    // ================================================================================
    // POST-BUILD ACTIONS
    // Cleanup and notifications that run regardless of build result
    // ================================================================================
    post {
        always {
            echo "${COLOR_CYAN}[PIPELINE] Completed${COLOR_RESET}"
            
            script {
                echo "${COLOR_YELLOW}[DOCKER CLEANUP] Starting Docker cleanup...${COLOR_RESET}"
                
                try {
                    // Remove temporary files
                    echo "${COLOR_YELLOW}[DOCKER CLEANUP] Removing temporary files...${COLOR_RESET}"
                    bat 'del /Q *_tag.txt 2>nul || exit 0'
                    bat 'del /Q *_hash.txt 2>nul || exit 0'
                    
                    // Remove local Docker images to save disk space
                    if (env.APPS_TO_BUILD) {
                        echo "${COLOR_YELLOW}[DOCKER CLEANUP] Removing local Docker images...${COLOR_RESET}"
                        def apps = env.APPS_TO_BUILD.split(',')
                        
                        apps.each { app ->
                            def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${app}"
                            def imageTag = ''
                            
                            if (env.DEPLOY_ENV == 'latest') {
                                imageTag = 'latest'
                            } else {
                                def cleanBranchName = env.GIT_BRANCH_NAME
                                    .replaceAll('[^a-zA-Z0-9._-]', '-')
                                    .toLowerCase()
                                imageTag = cleanBranchName
                            }
                            
                            try {
                                bat "docker rmi ${imageName}:${imageTag} 2>nul || exit 0"
                            } catch (Exception e) {
                                // Ignore errors during cleanup
                            }
                        }
                    }
                    
                    // Clean up dangling images
                    echo "${COLOR_YELLOW}[DOCKER CLEANUP] Removing dangling images...${COLOR_RESET}"
                    bat 'docker image prune -f 2>nul || exit 0'
                    
                    // Clean up old build cache
                    echo "${COLOR_YELLOW}[DOCKER CLEANUP] Cleaning Docker build cache...${COLOR_RESET}"
                    bat 'docker builder prune -f --filter "until=168h" 2>nul || exit 0'
                    
                    echo "${COLOR_GREEN}[DOCKER CLEANUP] Cleanup completed successfully${COLOR_RESET}"
                    
                } catch (Exception e) {
                    echo "${COLOR_RED}[ERROR] Docker cleanup failed: ${e.message}${COLOR_RESET}"
                }
                
                // Clean workspace to ensure fresh checkout next time
                // This ensures no stale files affect future builds
                echo "${COLOR_YELLOW}[WORKSPACE] Cleaning workspace for next build...${COLOR_RESET}"
                deleteDir()
                echo "${COLOR_GREEN}[WORKSPACE] Workspace cleaned successfully${COLOR_RESET}"
            }
        }
        success {
            echo "${COLOR_GREEN}[SUCCESS] Pipeline executed successfully!${COLOR_RESET}"
            script {
                if (env.DEPLOY_ENV == 'latest') {
                    echo "${COLOR_MAGENTA}[NOTICE] Production deployment completed!${COLOR_RESET}"
                    // Add Slack/Email notification here if needed
                }
            }
        }
        failure {
            echo "${COLOR_RED}[FAILURE] Pipeline failed!${COLOR_RESET}"
            // Add notification here if needed
        }
    }
}

// ================================================================================
// HELPER FUNCTION: Calculate Content Hash
// Creates a hash representing the current state of an application
// Used to determine if Docker image needs rebuilding
// ================================================================================
def calculateAppContentHash(appDir) {
    try {
        // List of file patterns to include in hash calculation
        def filePatterns = ['*.py', '*.txt', 'Dockerfile', '*.json', '*.yml', '*.yaml', '*.sh', '*.sql']
        def combinedContent = ''
        
        // Read .dockerignore patterns if exists
        def dockerignorePath = "${appDir}/.dockerignore"
        def ignorePatterns = []
        if (fileExists(dockerignorePath)) {
            def dockerignore = readFile(dockerignorePath)
            ignorePatterns = dockerignore.split('\n').findAll { it.trim() && !it.startsWith('#') }
        }
        
        // Process each file pattern
        filePatterns.each { pattern ->
            try {
                def files = bat(
                    script: "@dir /b \"${appDir}\\${pattern}\" 2>nul || exit 0",
                    returnStdout: true
                ).trim().split('\r?\n')
                
                files.each { file ->
                    if (file && file.trim()) {
                        def filePath = "${appDir}/${file}"
                        def shouldInclude = true
                        
                        // Check against ignore patterns
                        ignorePatterns.each { ignorePattern ->
                            if (file.contains(ignorePattern.replace('*', ''))) {
                                shouldInclude = false
                            }
                        }
                        
                        if (shouldInclude && fileExists(filePath)) {
                            // Read file content and add to combined content
                            def content = readFile(filePath)
                            combinedContent += file + ':' + content.hashCode().toString() + ';'
                        }
                    }
                }
            } catch (Exception e) {
                // Ignore errors for missing file patterns
            }
        }
        
        // Also hash subdirectories if they exist
        def subdirs = ['src', 'lib', 'utils', 'config', 'scripts']
        subdirs.each { subdir ->
            def subdirPath = "${appDir}/${subdir}"
            if (fileExists(subdirPath)) {
                filePatterns.each { pattern ->
                    try {
                        def files = bat(
                            script: "@dir /b /s \"${subdirPath}\\${pattern}\" 2>nul || exit 0",
                            returnStdout: true
                        ).trim().split('\r?\n')
                        
                        files.each { file ->
                            if (file && file.trim() && fileExists(file)) {
                                def content = readFile(file)
                                def relativePath = file.replace(env.WORKSPACE + '\\', '')
                                combinedContent += relativePath + ':' + content.hashCode().toString() + ';'
                            }
                        }
                    } catch (Exception e) {
                        // Ignore errors for missing patterns
                    }
                }
            }
        }
        
        // Return hash of combined content
        // If no content found, use timestamp to force build
        if (combinedContent) {
            return combinedContent.hashCode().toString()
        } else {
            return new Date().getTime().toString()
        }
        
    } catch (Exception e) {
        echo "${COLOR_YELLOW}[WARNING] Could not calculate hash for ${appDir}: ${e.message}${COLOR_RESET}"
        // Return timestamp as fallback to ensure build happens
        return new Date().getTime().toString()
    }
}