pipeline {
    agent any

    parameters {
        // Manual trigger parameters
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
        // GitHub webhook trigger
        githubPush()
    }

    environment {
        // Docker configuration
        DOCKER_REGISTRY = 'trialqlk1tc.jfrog.io'
        DOCKER_REPO = 'dockertest-docker'

        // Artifactory credentials
        ARTIFACTORY_CREDS = credentials('artifactory-credentials')

        // Build configuration
        BUILD_NUMBER = "${BUILD_NUMBER}"
        TIMESTAMP = "${new Date().format('yyyyMMdd-HHmmss')}"
        
        // Initialize status flags
        NO_APPS = 'false'
    }

    stages {
        stage('Initialize') {
            steps {
                script {
                    echo "========================================="
                    echo "BUILD INITIALIZATION"
                    echo "========================================="
                    echo "Build Number: ${BUILD_NUMBER}"
                    echo "Manual Branch Override: ${params.BRANCH_NAME ?: 'none'}"
                    echo "Deploy Target: ${params.DEPLOY_TARGET}"
                    echo "Force Build: ${params.FORCE_BUILD}"
                    echo "========================================="
                }
            }
        }

        stage('Checkout') {
            steps {
                script {
                    // If manual branch specified, checkout that branch
                    if (params.BRANCH_NAME) {
                        echo "[CHECKOUT] Checking out specified branch: ${params.BRANCH_NAME}"
                        checkout([
                            $class: 'GitSCM',
                            branches: [[name: "*/${params.BRANCH_NAME}"]],
                            extensions: [],
                            userRemoteConfigs: scm.userRemoteConfigs
                        ])
                        env.GIT_BRANCH_NAME = params.BRANCH_NAME
                    } else {
                        echo "[CHECKOUT] Checking out from webhook trigger..."
                        checkout scm
                        
                        // Get current branch name
                        try {
                            env.GIT_BRANCH_NAME = bat(
                                script: '@git rev-parse --abbrev-ref HEAD',
                                returnStdout: true
                            ).trim()
                            
                            // If HEAD is returned, try to get the actual branch name
                            if (env.GIT_BRANCH_NAME == 'HEAD') {
                                env.GIT_BRANCH_NAME = bat(
                                    script: '@git branch -r --contains HEAD',
                                    returnStdout: true
                                ).trim()
                                // Clean up the branch name (remove origin/ and any whitespace)
                                env.GIT_BRANCH_NAME = env.GIT_BRANCH_NAME.replaceAll('.*origin/', '').trim()
                            }
                        } catch (Exception e) {
                            env.GIT_BRANCH_NAME = 'unknown'
                        }
                    }

                    // Clean branch name (remove origin/ prefix if present)
                    if (env.GIT_BRANCH_NAME.contains('/')) {
                        def parts = env.GIT_BRANCH_NAME.split('/')
                        if (parts[0] == 'origin') {
                            env.GIT_BRANCH_NAME = parts[1..-1].join('/')
                        }
                    }

                    // Get commit information
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

                    echo "[BRANCH] ${env.GIT_BRANCH_NAME}"
                    echo "[COMMIT] ${env.GIT_COMMIT_HASH}"
                    echo "[AUTHOR] ${env.GIT_AUTHOR}"
                    echo "[MESSAGE] ${env.GIT_COMMIT_MSG}"

                    // Determine deployment target
                    if (params.DEPLOY_TARGET != 'auto') {
                        // Manual override
                        env.DEPLOY_ENV = params.DEPLOY_TARGET
                        echo "[DEPLOY] Manual override: deploying to '${env.DEPLOY_ENV}'"
                    } else {
                        // Auto-determine based on branch
                        if (env.GIT_BRANCH_NAME == 'main' || env.GIT_BRANCH_NAME == 'master') {
                            env.DEPLOY_ENV = 'latest'
                            echo "[DEPLOY] Main branch detected: deploying to 'latest'"
                        } else {
                            env.DEPLOY_ENV = 'dev'
                            echo "[DEPLOY] Feature branch detected: deploying to 'dev' with branch tag"
                        }
                    }
                }
            }
        }

        stage('Detect Changes') {
            steps {
                script {
                    echo "[DISCOVERY] Scanning for Python applications..."

                    def pythonApps = []
                    def changedApps = []

                    // Find all directories with Dockerfile
                    def dockerfiles = ''
                    try {
                        dockerfiles = bat(
                            script: '@dir /s /b Dockerfile 2>nul || exit 0',
                            returnStdout: true
                        ).trim()
                    } catch (Exception e) {
                        echo "[INFO] No Dockerfiles found in repository"
                        dockerfiles = ''
                    }

                    if (dockerfiles) {
                        dockerfiles.split('\r?\n').each { file ->
                            if (file && file.trim()) {  // Check if line is not empty
                                def relativePath = file.replace(env.WORKSPACE + '\\', '').replace('\\', '/')
                                def parts = relativePath.split('/')
                                // Only consider Dockerfiles in immediate subdirectories
                                if (parts.length == 2 && parts[1] == 'Dockerfile') {
                                    def appName = parts[0]
                                    if (!appName.startsWith('.')) {
                                        pythonApps.add(appName)
                                    }
                                }
                            }
                        }
                    }

                    echo "[APPS] Found ${pythonApps.size()} applications: ${pythonApps.join(', ')}"

                    // Exit early if no applications found
                    if (pythonApps.size() == 0) {
                        env.HAS_CHANGES = 'false'
                        env.NO_APPS = 'true'
                        echo "[INFO] No applications with Dockerfiles found in repository"
                        echo "[INFO] Pipeline will complete without building any images"
                        return
                    }

                    // Detect changes or force build
                    if (params.FORCE_BUILD) {
                        echo "[FORCE_BUILD] Building all applications"
                        changedApps = pythonApps
                    } else {
                        // Check for changes
                        try {
                            def commitCount = bat(
                                script: '@git rev-list --count HEAD',
                                returnStdout: true
                            ).trim()

                            if (commitCount == '1') {
                                echo "[FIRST_COMMIT] Building all applications"
                                changedApps = pythonApps
                            } else {
                                // Get list of changed files
                                def gitDiff = bat(
                                    script: '@git diff --name-only HEAD~1 HEAD',
                                    returnStdout: true
                                ).trim()

                                if (gitDiff) {
                                    def changedFiles = gitDiff.split('\r?\n')
                                    
                                    echo "[CHANGED_FILES] ${changedFiles.size()} files changed:"
                                    changedFiles.each { file ->
                                        echo "  - ${file}"
                                    }
                                    
                                    // Determine which apps have changes
                                    changedFiles.each { file ->
                                        def parts = file.split('/')
                                        if (parts.length > 0) {
                                            def app = parts[0]
                                            if (pythonApps.contains(app) && !changedApps.contains(app)) {
                                                changedApps.add(app)
                                            }
                                        }
                                    }
                                }
                            }
                        } catch (Exception e) {
                            echo "[WARNING] Could not determine changes, building all applications"
                            changedApps = pythonApps
                        }
                    }

                    if (changedApps.size() > 0) {
                        env.APPS_TO_BUILD = changedApps.join(',')
                        env.HAS_CHANGES = 'true'
                        echo "[BUILD_LIST] Applications to build: ${env.APPS_TO_BUILD}"
                    } else {
                        env.HAS_CHANGES = 'false'
                        echo "[INFO] No changes detected in any application"
                    }
                }
            }
        }

        stage('Build Docker Images') {
            when {
                environment name: 'HAS_CHANGES', value: 'true'
            }
            steps {
                script {
                    echo "[DOCKER] Building Docker images..."

                    def apps = env.APPS_TO_BUILD.split(',')
                    def buildJobs = [:]

                    apps.each { app ->
                        buildJobs[app] = {
                            echo "[BUILD] Building ${app}..."

                            // Determine the tag based on environment and branch
                            def imageTag = ''
                            
                            if (env.DEPLOY_ENV == 'latest') {
                                // For latest, always use 'latest' tag
                                imageTag = 'latest'
                            } else {
                                // For dev, use the branch name as tag
                                // Clean branch name for use as Docker tag
                                def cleanBranchName = env.GIT_BRANCH_NAME
                                    .replaceAll('[^a-zA-Z0-9._-]', '-')
                                    .toLowerCase()
                                imageTag = cleanBranchName
                            }

                            def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${app}"

                            try {
                                // Create requirements.txt if it doesn't exist
                                if (!fileExists("${app}/requirements.txt")) {
                                    writeFile file: "${app}/requirements.txt", text: "# No dependencies\n"
                                }

                                // Build the Docker image
                                bat "docker build -t ${imageName}:${imageTag} -f ${app}/Dockerfile ${app}/"
                                
                                echo "[SUCCESS] Built ${imageName}:${imageTag}"
                                
                                // Store tag for push stage
                                writeFile file: "${app}_tag.txt", text: imageTag

                            } catch (Exception e) {
                                echo "[ERROR] Failed to build ${app}: ${e.message}"
                                throw e
                            }
                        }
                    }

                    parallel buildJobs
                    env.BUILD_COMPLETE = 'true'
                }
            }
        }

        stage('Push to Artifactory') {
            when {
                environment name: 'BUILD_COMPLETE', value: 'true'
            }
            steps {
                script {
                    echo "[PUSH] Pushing images to Artifactory..."

                    def apps = env.APPS_TO_BUILD.split(',')

                    // Login to Artifactory
                    withCredentials([usernamePassword(
                        credentialsId: 'artifactory-credentials',
                        usernameVariable: 'ARTIFACTORY_USER',
                        passwordVariable: 'ARTIFACTORY_PASS'
                    )]) {
                        bat 'echo %ARTIFACTORY_PASS% | docker login %DOCKER_REGISTRY% -u %ARTIFACTORY_USER% --password-stdin'
                        
                        echo "[LOGIN] Successfully logged into Artifactory"

                        def pushJobs = [:]

                        apps.each { app ->
                            pushJobs[app] = {
                                def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${app}"
                                def imageTag = readFile("${app}_tag.txt").trim()
                                
                                try {
                                    bat "docker push ${imageName}:${imageTag}"
                                    echo "[PUSHED] ${imageName}:${imageTag}"
                                    
                                    // Log for summary
                                    env."${app}_PUSHED_TAG" = imageTag
                                    
                                } catch (Exception e) {
                                    echo "[ERROR] Failed to push ${imageName}:${imageTag}: ${e.message}"
                                    throw e
                                }
                            }
                        }

                        parallel pushJobs
                    }

                    // Logout
                    bat "docker logout ${env.DOCKER_REGISTRY}"
                }
            }
        }

        stage('Cleanup Temp Files') {
            when {
                environment name: 'BUILD_COMPLETE', value: 'true'
            }
            steps {
                script {
                    echo "[CLEANUP] Cleaning up temporary files..."
                    
                    try {
                        // Remove temporary tag files
                        bat 'del /Q *_tag.txt 2>nul || exit 0'
                        
                    } catch (Exception e) {
                        echo "[WARNING] Temp file cleanup failed: ${e.message}"
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
                    echo "Branch: ${env.GIT_BRANCH_NAME}"
                    echo "Commit: ${env.GIT_COMMIT_HASH}"
                    echo "Author: ${env.GIT_AUTHOR}"
                    echo "Build #: ${env.BUILD_NUMBER}"
                    echo "Target: ${env.DEPLOY_ENV}"
                    
                    if (params.BRANCH_NAME) {
                        echo "Manual Branch Override: ${params.BRANCH_NAME}"
                    }

                    if (env.NO_APPS == 'true') {
                        echo "\nStatus: No applications with Dockerfiles found in repository"
                        echo "Add applications with Dockerfiles to enable Docker builds"
                    } else if (env.HAS_CHANGES == 'true') {
                        echo "\nApplications Built and Pushed:"
                        def apps = env.APPS_TO_BUILD.split(',')
                        apps.each { app ->
                            def pushedTag = env."${app}_PUSHED_TAG"
                            echo "  ${app}:"
                            echo "    Image: ${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${app}:${pushedTag}"
                            echo "    Registry URL: https://${env.DOCKER_REGISTRY}/artifactory/webapp/#/artifacts/browse/tree/General/${env.DOCKER_REPO}/${app}"
                        }
                        
                        echo "\nTo pull images:"
                        apps.each { app ->
                            def pushedTag = env."${app}_PUSHED_TAG"
                            echo "  docker pull ${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${app}:${pushedTag}"
                        }
                    } else {
                        echo "\nStatus: No changes detected in applications"
                    }
                    
                    echo "========================================="

                    // Update build description
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

    post {
        always {
            echo "[PIPELINE] Completed"
            
            script {
                echo "[DOCKER CLEANUP] Starting Docker cleanup..."
                
                try {
                    // Stop and remove any running containers from this build
                    def runningContainers = bat(
                        script: '@docker ps -a -q --filter "label=jenkins.build=${BUILD_NUMBER}" 2>nul',
                        returnStdout: true
                    ).trim()
                    
                    if (runningContainers) {
                        echo "[DOCKER CLEANUP] Stopping and removing containers..."
                        bat "docker rm -f ${runningContainers}"
                    }
                    
                    // Remove images that were built in this pipeline
                    if (env.APPS_TO_BUILD) {
                        echo "[DOCKER CLEANUP] Removing built images..."
                        def apps = env.APPS_TO_BUILD.split(',')
                        
                        apps.each { app ->
                            def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${app}"
                            
                            // Get the tag that was used
                            def imageTag = ''
                            if (fileExists("${app}_tag.txt")) {
                                imageTag = readFile("${app}_tag.txt").trim()
                            } else if (env.DEPLOY_ENV == 'latest') {
                                imageTag = 'latest'
                            } else {
                                def cleanBranchName = env.GIT_BRANCH_NAME
                                    .replaceAll('/', '-')
                                    .replaceAll('[^a-zA-Z0-9._-]', '')
                                    .toLowerCase()
                                imageTag = cleanBranchName
                            }
                            
                            try {
                                echo "[DOCKER CLEANUP] Removing ${imageName}:${imageTag}"
                                bat "docker rmi ${imageName}:${imageTag} 2>nul || exit 0"
                            } catch (Exception e) {
                                echo "[WARNING] Could not remove ${imageName}:${imageTag}"
                            }
                        }
                    }
                    
                    // Remove all dangling images (untagged images)
                    echo "[DOCKER CLEANUP] Removing dangling images..."
                    bat 'docker image prune -f 2>nul || exit 0'
                    
                    // Optional: Remove all unused images (commented out as it might be too aggressive)
                    // bat 'docker image prune -a -f --filter "until=24h" 2>nul || exit 0'
                    
                    // Clean up build cache to free space
                    echo "[DOCKER CLEANUP] Cleaning Docker build cache..."
                    bat 'docker builder prune -f --filter "until=24h" 2>nul || exit 0'
                    
                    // Remove temporary files
                    echo "[DOCKER CLEANUP] Removing temporary files..."
                    bat 'del /Q *_tag.txt 2>nul || exit 0'
                    
                    // Show remaining Docker images for debugging
                    echo "[DOCKER CLEANUP] Remaining Docker images:"
                    bat 'docker images --format "table {{.Repository}}:{{.Tag}}\\t{{.Size}}\\t{{.CreatedAt}}" 2>nul || echo No images found'
                    
                    echo "[DOCKER CLEANUP] Cleanup completed successfully"
                    
                } catch (Exception e) {
                    echo "[ERROR] Docker cleanup failed: ${e.message}"
                    echo "[INFO] Manual cleanup may be required"
                }
            }
        }
        success {
            echo "[SUCCESS] Pipeline executed successfully!"
            script {
                if (env.DEPLOY_ENV == 'latest') {
                    echo "[NOTICE] Production deployment completed!"
                    // Add notification here if needed (Slack, Email, etc.)
                }
            }
        }
        failure {
            echo "[FAILURE] Pipeline failed!"
            // Add notification here if needed
        }
    }
}