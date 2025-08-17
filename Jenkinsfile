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
    }

    stages {
        // ================================================================================
        // STAGE 1: Initialize Pipeline
        // ================================================================================
        stage('Initialize') {
            steps {
                script {
                    echo "========================================="
                    echo ">>> BUILD INITIALIZATION"
                    echo "========================================="
                    echo "Build Number: ${BUILD_NUMBER}"
                    echo "Manual Branch Override: ${params.BRANCH_NAME ?: 'none'}"
                    echo "Deploy Target: ${params.DEPLOY_TARGET}"
                    echo "========================================="
                }
            }
        }

        // ================================================================================
        // STAGE 2: Checkout Code
        // ================================================================================
        stage('Checkout') {
            steps {
                script {
                    // Clean workspace before checkout to ensure fresh state
                    echo "[WORKSPACE] Cleaning previous workspace..."
                    deleteDir()
                    
                    // Handle manual branch override vs webhook trigger
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
                        
                        // Determine current branch name from git
                        try {
                            env.GIT_BRANCH_NAME = bat(
                                script: 'git rev-parse --abbrev-ref HEAD',
                                returnStdout: true
                            ).trim()
                            
                            // Handle detached HEAD state
                            if (env.GIT_BRANCH_NAME == 'HEAD') {
                                env.GIT_BRANCH_NAME = bat(
                                    script: 'git branch -r --contains HEAD',
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
                        // Using full git command for better reliability
                        env.GIT_COMMIT_HASH = bat(
                            script: 'git rev-parse --short=8 HEAD',
                            returnStdout: true
                        ).trim()
                        // CORRECTED: Escaped %B to %%B for Windows compatibility
                        env.GIT_COMMIT_MSG = bat(
                            script: 'git log -1 --pretty=%%B',
                            returnStdout: true
                        ).trim()
                        env.GIT_AUTHOR = bat(
                            script: 'git log -1 --pretty=%%an',
                            returnStdout: true
                        ).trim()
                    } catch (Exception e) {
                        error("Failed to get Git commit information. Error: ${e.message}")
                        env.GIT_COMMIT_HASH = "unknown"
                        env.GIT_COMMIT_MSG = "Unknown"
                        env.GIT_AUTHOR = "Unknown"
                    }

                    echo "[BRANCH] ${env.GIT_BRANCH_NAME}"
                    echo "[COMMIT] ${env.GIT_COMMIT_HASH}"
                    echo "[AUTHOR] ${env.GIT_AUTHOR}"
                    echo "[MESSAGE] ${env.GIT_COMMIT_MSG}"

                    // Determine deployment environment based on branch or manual override
                    if (params.DEPLOY_TARGET != 'auto') {
                        env.DEPLOY_ENV = params.DEPLOY_TARGET
                        echo "[DEPLOY] Manual override: deploying to '${env.DEPLOY_ENV}'"
                    } else {
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

        // ================================================================================
        // STAGE 3: Detect Changes (IMPROVED LOGIC)
        // Scans for apps and uses 'git diff' to detect changes in each app's directory
        // since the last successful build for that specific app.
        // ================================================================================
        stage('Detect Changes') {
            steps {
                script {
                    echo "========================================="
                    echo ">>> PER-APP CHANGE DETECTION (GIT DIFF BASED)"
                    echo "========================================="
                    echo "[DISCOVERY] Scanning for applications..."

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
                        echo "[INFO] No Dockerfiles found in repository"
                        dockerfiles = ''
                    }

                    // Process found Dockerfiles to identify applications
                    if (dockerfiles) {
                        dockerfiles.split('\r?\n').each { file ->
                            if (file && file.trim()) {
                                def relativePath = file.replace(env.WORKSPACE + '\\', '').replace('\\', '/')
                                def parts = relativePath.split('/')
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

                    if (pythonApps.size() == 0) {
                        env.HAS_CHANGES = 'false'
                        env.NO_APPS = 'true'
                        echo "[INFO] No applications with Dockerfiles found in repository"
                        return
                    }

                    withCredentials([usernamePassword(
                        credentialsId: 'artifactory-credentials',
                        usernameVariable: 'ARTIFACTORY_USER',
                        passwordVariable: 'ARTIFACTORY_PASS'
                    )]) {
                        bat 'echo %ARTIFACTORY_PASS% | docker login %DOCKER_REGISTRY% -u %ARTIFACTORY_USER% --password-stdin'

                        pythonApps.each { app ->
                            def needsBuild = false
                            def currentCommit = env.GIT_COMMIT_HASH

                            def imageTag = (env.DEPLOY_ENV == 'latest') ? 'latest' : env.GIT_BRANCH_NAME.replaceAll('[^a-zA-Z0-9._-]', '-').toLowerCase()
                            def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${app}:${imageTag}"

                            try {
                                def pullResult = bat(script: "docker pull ${imageName} 2>&1", returnStatus: true)

                                if (pullResult == 0) {
                                    def lastBuiltCommit = bat(
                                        script: "docker inspect ${imageName} --format=\"{{index .Config.Labels \\\"git.commit\\\"}}\" 2>nul || echo \"\"",
                                        returnStdout: true
                                    ).trim()

                                    if (lastBuiltCommit && lastBuiltCommit != "unknown") {
                                        echo "[INFO] ${app}: Last build was from commit ${lastBuiltCommit}. Comparing with current commit ${currentCommit}."
                                        // Use git diff to check for changes in the specific app directory.
                                        // returnStatus: true makes it return the exit code. 0 = no changes, 1 = changes.
                                        def diffResult = bat(
                                            script: "git diff --quiet ${lastBuiltCommit} ${currentCommit} -- ./${app}",
                                            returnStatus: true
                                        )

                                        if (diffResult != 0) {
                                            echo "[CHANGE DETECTED] ${app}: Code changes found in ./${app} since commit ${lastBuiltCommit}."
                                            needsBuild = true
                                        } else {
                                            echo "[NO CHANGE] ${app}: No code changes in ./${app} since last build."
                                        }
                                    } else {
                                        echo "[CHANGE DETECTED] ${app}: No valid git.commit label on existing image. Rebuilding."
                                        needsBuild = true
                                    }
                                    
                                    bat "docker rmi ${imageName} 2>nul || exit 0" // Clean up pulled image
                                } else {
                                    echo "[NEW IMAGE] ${app}: Image does not exist in registry. Building."
                                    needsBuild = true
                                }
                            } catch (e) {
                                echo "[ERROR] ${app}: Error during change detection. Assuming build is needed. Details: ${e.message}"
                                needsBuild = true
                            }

                            if (needsBuild) {
                                changedApps.add(app)
                            }
                        }

                        bat "docker logout ${env.DOCKER_REGISTRY}"
                    }

                    if (changedApps.size() > 0) {
                        env.APPS_TO_BUILD = changedApps.join(',')
                        env.HAS_CHANGES = 'true'
                        echo "========================================="
                        echo "[BUILD LIST] Applications to build: ${env.APPS_TO_BUILD}"
                        echo "========================================="
                    } else {
                        env.HAS_CHANGES = 'false'
                        echo "========================================="
                        echo "[RESULT] No applications need building - all content is up to date"
                        echo "========================================="
                    }
                }
            }
        }

        // ================================================================================
        // STAGE 4: Build Docker Images
        // ================================================================================
        stage('Build Docker Images') {
            when {
                environment name: 'HAS_CHANGES', value: 'true'
            }
            steps {
                script {
                    echo "========================================="
                    echo ">>> DOCKER BUILD"
                    echo "========================================="

                    def apps = env.APPS_TO_BUILD.split(',')
                    def buildJobs = [:]

                    apps.each { app ->
                        buildJobs[app] = {
                            echo "[BUILD START] ${app}"
                            def imageTag = (env.DEPLOY_ENV == 'latest') ? 'latest' : env.GIT_BRANCH_NAME.replaceAll('[^a-zA-Z0-9._-]', '-').toLowerCase()
                            def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${app}"

                            try {
                                if (!fileExists("${app}/requirements.txt")) {
                                    writeFile file: "${app}/requirements.txt", text: "# No dependencies\n"
                                }

                                bat """
                                    docker build \
                                        -t ${imageName}:${imageTag} \
                                        --label git.commit=${env.GIT_COMMIT_HASH} \
                                        --label git.branch=${env.GIT_BRANCH_NAME} \
                                        --label build.number=${BUILD_NUMBER} \
                                        --label build.timestamp=${env.TIMESTAMP} \
                                        -f ${app}/Dockerfile ${app}/
                                """
                                
                                echo "[BUILD SUCCESS] ${app}: ${imageName}:${imageTag} (commit: ${env.GIT_COMMIT_HASH})"
                                writeFile file: "${app}_tag.txt", text: imageTag

                            } catch (Exception e) {
                                echo "[BUILD ERROR] ${app}: ${e.message}"
                                throw e
                            }
                        }
                    }

                    parallel buildJobs
                    env.BUILD_COMPLETE = 'true'
                }
            }
        }

        // ================================================================================
        // STAGE 5: Push to Artifactory
        // ================================================================================
        stage('Push to Artifactory') {
            when {
                environment name: 'BUILD_COMPLETE', value: 'true'
            }
            steps {
                script {
                    echo "========================================="
                    echo ">>> ARTIFACTORY PUSH"
                    echo "========================================="
                    def apps = env.APPS_TO_BUILD.split(',')

                    withCredentials([usernamePassword(
                        credentialsId: 'artifactory-credentials',
                        usernameVariable: 'ARTIFACTORY_USER',
                        passwordVariable: 'ARTIFACTORY_PASS'
                    )]) {
                        bat 'echo %ARTIFACTORY_PASS% | docker login %DOCKER_REGISTRY% -u %ARTIFACTORY_USER% --password-stdin'
                        def pushJobs = [:]
                        apps.each { app ->
                            pushJobs[app] = {
                                def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${app}"
                                def imageTag = readFile("${app}_tag.txt").trim()
                                
                                try {
                                    bat "docker push ${imageName}:${imageTag}"
                                    echo "[PUSH SUCCESS] ${app}: ${imageName}:${imageTag}"
                                    env."${app}_PUSHED_TAG" = imageTag
                                } catch (Exception e) {
                                    echo "[PUSH ERROR] ${app}: ${e.message}"
                                    throw e
                                }
                            }
                        }
                        parallel pushJobs
                    }
                    bat "docker logout ${env.DOCKER_REGISTRY}"
                }
            }
        }

        // ================================================================================
        // STAGE 6: Cleanup Temporary Files
        // ================================================================================
        stage('Cleanup Temp Files') {
            when {
                environment name: 'BUILD_COMPLETE', value: 'true'
            }
            steps {
                script {
                    echo "[CLEANUP] Cleaning up temporary files..."
                    try {
                        bat 'del /Q *_tag.txt 2>nul || exit 0'
                        echo "[CLEANUP] Temporary files removed"
                    } catch (Exception e) {
                        echo "[CLEANUP WARNING] Temp file cleanup failed: ${e.message}"
                    }
                }
            }
        }

        // ================================================================================
        // STAGE 7: Build Summary
        // ================================================================================
        stage('Summary') {
            steps {
                script {
                    echo "\n========================================="
                    echo ">>> BUILD SUMMARY"
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
                        echo "\n[STATUS] No applications with Dockerfiles found in repository"
                    } else if (env.HAS_CHANGES == 'true') {
                        echo "\n>>> APPLICATIONS BUILT AND PUSHED:"
                        def apps = env.APPS_TO_BUILD.split(',')
                        apps.each { app ->
                            def pushedTag = env."${app}_PUSHED_TAG"
                            echo "\n   ${app}:"
                            echo "     Image: ${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${app}:${pushedTag}"
                            echo "     Registry: https://${env.DOCKER_REGISTRY}/artifactory/webapp/#/artifacts/browse/tree/General/${env.DOCKER_REPO}/${app}"
                        }
                        
                        echo "\n>>> TO PULL IMAGES:"
                        apps.each { app ->
                            def pushedTag = env."${app}_PUSHED_TAG"
                            echo "   docker pull ${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${app}:${pushedTag}"
                        }
                    } else {
                        echo "\n[STATUS] No changes detected - all applications are up to date"
                    }
                    
                    echo "========================================="

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
    // ================================================================================
    post {
        always {
            echo "[PIPELINE] Completed"
            
            script {
                echo "[DOCKER CLEANUP] Starting Docker cleanup..."
                
                try {
                    bat 'del /Q *_tag.txt 2>nul || exit 0'
                    if (env.APPS_TO_BUILD) {
                        echo "[DOCKER CLEANUP] Removing local Docker images..."
                        def apps = env.APPS_TO_BUILD.split(',')
                        apps.each { app ->
                            def imageTag = (env.DEPLOY_ENV == 'latest') ? 'latest' : env.GIT_BRANCH_NAME.replaceAll('[^a-zA-Z0-9._-]', '-').toLowerCase()
                            def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${app}"
                            try {
                                bat "docker rmi ${imageName}:${imageTag} 2>nul || exit 0"
                            } catch (Exception e) {
                                // Ignore errors
                            }
                        }
                    }
                    
                    echo "[DOCKER CLEANUP] Pruning Docker cache..."
                    bat 'docker image prune -f 2>nul || exit 0'
                    bat 'docker builder prune -f --filter "until=168h" 2>nul || exit 0'
                    echo "[DOCKER CLEANUP] Cleanup completed"
                } catch (Exception e) {
                    echo "[DOCKER CLEANUP ERROR] ${e.message}"
                }
                
                echo "[WORKSPACE] Cleaning workspace for next build..."
                deleteDir()
                echo "[WORKSPACE] Workspace cleaned successfully"
            }
        }
        success {
            echo "[SUCCESS] Pipeline executed successfully!"
        }
        failure {
            echo "[FAILURE] Pipeline failed!"
        }
    }
}
