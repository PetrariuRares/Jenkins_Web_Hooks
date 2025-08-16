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
                    // Checkout the correct branch
                    if (params.BRANCH_NAME) {
                        echo "[CHECKOUT] Checking out specified branch: ${params.BRANCH_NAME}"
                        checkout([
                            $class: 'GitSCM',
                            branches: [[name: "*/${params.BRANCH_NAME}"]],
                            extensions: [],
                            userRemoteConfigs: scm.userRemoteConfigs
                        ])
                        // Set the branch name from the parameter for consistency
                        env.GIT_BRANCH_NAME = params.BRANCH_NAME
                    } else {
                        echo "[CHECKOUT] Checking out from webhook trigger..."
                        checkout scm
                        // *** FIX: More reliable branch name detection for detached HEAD scenarios ***
                        try {
                             def branchOutput = bat(
                                script: '@git branch -r --contains HEAD',
                                returnStdout: true
                            ).trim()
                            // The output might be like "  origin/main" or "* origin/feature/branch", so we clean it up
                            env.GIT_BRANCH_NAME = branchOutput.split('\n')[0].replaceAll('^\\s*origin/', '').replaceAll('^\\*\\s*', '').trim()
                        } catch (e) {
                            echo "[ERROR] Could not determine branch name. Defaulting to 'unknown'."
                            env.GIT_BRANCH_NAME = 'unknown'
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

                    // Find all directories with a Dockerfile in the root
                    def appDirs = bat(script: '@dir /b /ad', returnStdout: true).trim().split('\r?\n')
                    appDirs.each { dir ->
                        if (fileExists("${dir}/Dockerfile") && !dir.startsWith('.')) {
                            pythonApps.add(dir)
                        }
                    }
                    
                    echo "[APPS] Found ${pythonApps.size()} applications: ${pythonApps.join(', ')}"

                    // Exit early if no applications found
                    if (pythonApps.isEmpty()) {
                        env.HAS_CHANGES = 'false'
                        env.NO_APPS = 'true'
                        echo "[INFO] No applications with Dockerfiles found in repository"
                        return
                    }

                    // Detect changes or force build
                    if (params.FORCE_BUILD) {
                        echo "[FORCE_BUILD] Building all applications"
                        changedApps = pythonApps
                    } else {
                        // *** FIX: Correctly iterate through change sets to get affected paths ***
                        def changedFiles = []
                        if (currentBuild.changeSets.isEmpty()) {
                            echo "[INFO] No changesets found. This might be the first build. Building all apps."
                            changedApps = pythonApps
                        } else {
                            for (changeSet in currentBuild.changeSets) {
                                for (entry in changeSet.items) {
                                    // 'affectedPaths' is a collection of strings (the file paths)
                                    for (path in entry.affectedPaths) {
                                        changedFiles.add(path)
                                    }
                                }
                            }
                        }

                        if (!changedFiles.isEmpty()) {
                            echo "[CHANGED_FILES] ${changedFiles.size()} files changed:"
                            changedFiles.each { file -> echo "  - ${file}" }
                            
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

                    if (!changedApps.isEmpty()) {
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
                expression { env.HAS_CHANGES == 'true' }
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
                                imageTag = 'latest'
                            } else {
                                // Clean branch name for use as Docker tag
                                def cleanBranchName = env.GIT_BRANCH_NAME
                                    .replaceAll('/', '-') // Replace slashes first
                                    .replaceAll('[^a-zA-Z0-9._-]', '') // Remove other invalid characters
                                    .toLowerCase()
                                imageTag = cleanBranchName
                            }

                            def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${app}"

                            try {
                                // Build the Docker image
                                bat "docker build -t ${imageName}:${imageTag} -f ${app}/Dockerfile ${app}/"
                                
                                echo "[SUCCESS] Built ${imageName}:${imageTag}"
                                
                                // Store tag for push stage
                                writeFile file: "${app}_tag.txt", text: imageTag

                            } catch (Exception e) {
                                echo "[ERROR] Failed to build ${app}: ${e.message}"
                                error "Build failed for ${app}"
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
                expression { env.BUILD_COMPLETE == 'true' }
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
                                    error "Push failed for ${app}"
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

        stage('Cleanup') {
            when {
                expression { env.BUILD_COMPLETE == 'true' }
            }
            steps {
                script {
                    echo "[CLEANUP] Cleaning up local images and temporary files..."
                    
                    try {
                        // Remove dangling images
                        bat 'docker image prune -f'
                        
                        // Remove temporary tag files
                        bat 'del /Q *_tag.txt 2>nul || exit 0'
                        
                    } catch (Exception e) {
                        echo "[WARNING] Cleanup failed: ${e.message}"
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
        }
        success {
            echo "[SUCCESS] Pipeline executed successfully!"
        }
        failure {
            echo "[FAILURE] Pipeline failed!"
        }
    }
}
