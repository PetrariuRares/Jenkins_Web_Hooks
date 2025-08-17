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
        // Sets up the build environment and displays configuration
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
        // Handles both manual branch selection and webhook triggers
        // Determines deployment target based on branch name
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
                            script: '@git rev-parse HEAD',
                            returnStdout: true
                        ).trim()
                        env.GIT_COMMIT_SHORT = bat(
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
                        env.GIT_COMMIT_HASH = "unknown"
                        env.GIT_COMMIT_SHORT = "unknown-${BUILD_NUMBER}"
                        env.GIT_COMMIT_MSG = "Unknown"
                        env.GIT_AUTHOR = "Unknown"
                    }

                    echo "[BRANCH] ${env.GIT_BRANCH_NAME}"
                    echo "[COMMIT] ${env.GIT_COMMIT_SHORT} (${env.GIT_COMMIT_HASH})"
                    echo "[AUTHOR] ${env.GIT_AUTHOR}"
                    echo "[MESSAGE] ${env.GIT_COMMIT_MSG}"

                    // Determine deployment environment based on branch or manual override
                    if (params.DEPLOY_TARGET != 'auto') {
                        // Manual deployment target override
                        env.DEPLOY_ENV = params.DEPLOY_TARGET
                        echo "[DEPLOY] Manual override: deploying to '${env.DEPLOY_ENV}'"
                    } else {
                        // Auto-determine based on branch naming convention
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
        // STAGE 3: Detect Changes
        // Scans for applications with Dockerfiles
        // Compares git commits between current code and Artifactory images
        // Uses git diff to determine which specific apps have changes
        // ================================================================================
        stage('Detect Changes') {
            steps {
                script {
                    echo "========================================="
                    echo ">>> CHANGE DETECTION"
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

                    echo "[APPS] Found ${pythonApps.size()} applications: ${pythonApps.join(', ')}"

                    // Exit early if no applications found
                    if (pythonApps.size() == 0) {
                        env.HAS_CHANGES = 'false'
                        env.NO_APPS = 'true'
                        echo "[INFO] No applications with Dockerfiles found in repository"
                        echo "[INFO] Pipeline will complete without building any images"
                        return
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
                            def needsBuild = false
                            def reason = ""

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

                            // Check if image exists in registry and compare git commits
                            try {
                                // Attempt to pull the image from registry
                                def pullResult = bat(
                                    script: "docker pull ${imageName} 2>&1",
                                    returnStatus: true
                                )

                                if (pullResult == 0) {
                                    // Image exists, extract git commit from labels
                                    def existingCommit = bat(
                                        script: "@docker inspect ${imageName} --format=\"{{index .Config.Labels \\\"git.commit\\\"}}\" 2>nul || echo \"\"",
                                        returnStdout: true
                                    ).trim()

                                    if (!existingCommit) {
                                        // No commit label in existing image
                                        needsBuild = true
                                        reason = "No git.commit label in existing image"
                                    } else if (existingCommit == env.GIT_COMMIT_HASH) {
                                        // Same commit, no changes
                                        needsBuild = false
                                        reason = "Same commit (${env.GIT_COMMIT_SHORT})"
                                    } else {
                                        // Different commit - check if this specific app changed
                                        echo "[DIFF] Checking changes for ${app} between ${existingCommit.take(8)} and ${env.GIT_COMMIT_SHORT}"
                                        
                                        def hasChanges = checkAppChanges(app, existingCommit, env.GIT_COMMIT_HASH)
                                        
                                        if (hasChanges) {
                                            needsBuild = true
                                            reason = "Changes detected (${existingCommit.take(8)} -> ${env.GIT_COMMIT_SHORT})"
                                        } else {
                                            needsBuild = false
                                            reason = "No changes in app directory (commits differ but app unchanged)"
                                        }
                                    }
                                    
                                    // Clean up pulled image to save space
                                    bat "docker rmi ${imageName} 2>nul || exit 0"
                                } else {
                                    // Image doesn't exist
                                    needsBuild = true
                                    reason = "Image doesn't exist in registry"
                                }
                            } catch (Exception e) {
                                // Error checking image
                                needsBuild = true
                                reason = "Unable to check existing image: ${e.message}"
                            }

                            // Log decision and add to build list if needed
                            if (needsBuild) {
                                echo "[BUILD NEEDED] ${app}: ${reason}"
                                changedApps.add(app)
                            } else {
                                echo "[SKIP] ${app}: ${reason}"
                            }
                        }

                        bat "docker logout ${env.DOCKER_REGISTRY}"
                    }

                    // Set environment variables based on detection results
                    if (changedApps.size() > 0) {
                        env.APPS_TO_BUILD = changedApps.join(',')
                        env.HAS_CHANGES = 'true'
                        echo "========================================="
                        echo "[BUILD LIST] Applications to build: ${env.APPS_TO_BUILD}"
                        echo "========================================="
                    } else {
                        env.HAS_CHANGES = 'false'
                        echo "========================================="
                        echo "[RESULT] No applications need building - all are up to date"
                        echo "========================================="
                    }
                }
            }
        }

        // ================================================================================
        // STAGE 4: Build Docker Images
        // Builds only the applications that have changes
        // Uses parallel execution for efficiency
        // Adds git commit as Docker label for future comparison
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

                    // Create parallel build jobs for each application
                    apps.each { app ->
                        buildJobs[app] = {
                            echo "[BUILD START] ${app}"

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
                                // Labels are used to track git commit and build information
                                bat """
                                    docker build \
                                        -t ${imageName}:${imageTag} \
                                        --label git.commit=${env.GIT_COMMIT_HASH} \
                                        --label git.branch=${env.GIT_BRANCH_NAME} \
                                        --label git.author="${env.GIT_AUTHOR}" \
                                        --label build.number=${BUILD_NUMBER} \
                                        --label build.timestamp=${env.TIMESTAMP} \
                                        --label description="${app} built from ${env.GIT_COMMIT_SHORT}" \
                                        -f ${app}/Dockerfile ${app}/
                                """
                                
                                echo "[BUILD SUCCESS] ${app}: ${imageName}:${imageTag}"
                                
                                // Store tag for push stage
                                writeFile file: "${app}_tag.txt", text: imageTag

                            } catch (Exception e) {
                                echo "[BUILD ERROR] ${app}: ${e.message}"
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
                    echo "========================================="
                    echo ">>> ARTIFACTORY PUSH"
                    echo "========================================="

                    def apps = env.APPS_TO_BUILD.split(',')

                    // Authenticate with Artifactory
                    withCredentials([usernamePassword(
                        credentialsId: 'artifactory-credentials',
                        usernameVariable: 'ARTIFACTORY_USER',
                        passwordVariable: 'ARTIFACTORY_PASS'
                    )]) {
                        bat 'echo %ARTIFACTORY_PASS% | docker login %DOCKER_REGISTRY% -u %ARTIFACTORY_USER% --password-stdin'
                        
                        echo "[LOGIN] Successfully logged into Artifactory"

                        def pushJobs = [:]

                        // Create parallel push jobs for each application
                        apps.each { app ->
                            pushJobs[app] = {
                                def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${app}"
                                def imageTag = readFile("${app}_tag.txt").trim()
                                
                                try {
                                    // Push image to registry
                                    bat "docker push ${imageName}:${imageTag}"
                                    echo "[PUSH SUCCESS] ${app}: ${imageName}:${imageTag}"
                                    
                                    // Store pushed tag for summary report
                                    env."${app}_PUSHED_TAG" = imageTag
                                    
                                } catch (Exception e) {
                                    echo "[PUSH ERROR] ${app}: ${e.message}"
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
                    echo "[CLEANUP] Cleaning up temporary files..."
                    
                    try {
                        // Remove temporary tag files
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
        // Displays comprehensive build results and instructions
        // ================================================================================
        stage('Summary') {
            steps {
                script {
                    echo "\n========================================="
                    echo ">>> BUILD SUMMARY"
                    echo "========================================="
                    echo "Branch: ${env.GIT_BRANCH_NAME}"
                    echo "Commit: ${env.GIT_COMMIT_SHORT}"
                    echo "Author: ${env.GIT_AUTHOR}"
                    echo "Build #: ${env.BUILD_NUMBER}"
                    echo "Target: ${env.DEPLOY_ENV}"
                    
                    if (params.BRANCH_NAME) {
                        echo "Manual Branch Override: ${params.BRANCH_NAME}"
                    }

                    // Display appropriate summary based on build results
                    if (env.NO_APPS == 'true') {
                        echo "\n[STATUS] No applications with Dockerfiles found in repository"
                        echo "Add applications with Dockerfiles to enable Docker builds"
                    } else if (env.HAS_CHANGES == 'true') {
                        echo "\n>>> APPLICATIONS BUILT AND PUSHED:"
                        def apps = env.APPS_TO_BUILD.split(',')
                        apps.each { app ->
                            def pushedTag = env."${app}_PUSHED_TAG"
                            echo "\n  ${app}:"
                            echo "    Image: ${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${app}:${pushedTag}"
                            echo "    Registry: https://${env.DOCKER_REGISTRY}/artifactory/webapp/#/artifacts/browse/tree/General/${env.DOCKER_REPO}/${app}"
                        }
                        
                        // Provide docker pull commands for easy access
                        echo "\n>>> TO PULL IMAGES:"
                        apps.each { app ->
                            def pushedTag = env."${app}_PUSHED_TAG"
                            echo "  docker pull ${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${app}:${pushedTag}"
                        }
                    } else {
                        echo "\n[STATUS] No changes detected - all applications are up to date"
                        echo "No builds performed, no new images pushed to Artifactory"
                    }
                    
                    echo "========================================="

                    // Update Jenkins build description for dashboard visibility
                    if (env.NO_APPS == 'true') {
                        currentBuild.description = "No apps found | ${env.GIT_BRANCH_NAME}"
                    } else if (env.HAS_CHANGES == 'true') {
                        currentBuild.description = "${env.DEPLOY_ENV} | ${env.GIT_BRANCH_NAME} | ${env.APPS_TO_BUILD}"
                    } else {
                        currentBuild.description = "No changes | ${env.GIT_BRANCH_NAME} | ${env.GIT_COMMIT_SHORT}"
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
            echo "[PIPELINE] Completed"
            
            script {
                echo "[DOCKER CLEANUP] Starting Docker cleanup..."
                
                try {
                    // Remove temporary files
                    echo "[DOCKER CLEANUP] Removing temporary files..."
                    bat 'del /Q *_tag.txt 2>nul || exit 0'
                    
                    // Remove local Docker images to save disk space
                    if (env.APPS_TO_BUILD) {
                        echo "[DOCKER CLEANUP] Removing local Docker images..."
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
                    echo "[DOCKER CLEANUP] Removing dangling images..."
                    bat 'docker image prune -f 2>nul || exit 0'
                    
                    // Clean up old build cache
                    echo "[DOCKER CLEANUP] Cleaning Docker build cache..."
                    bat 'docker builder prune -f --filter "until=168h" 2>nul || exit 0'
                    
                    echo "[DOCKER CLEANUP] Cleanup completed successfully"
                    
                } catch (Exception e) {
                    echo "[DOCKER CLEANUP ERROR] ${e.message}"
                }
                
                // Clean workspace to ensure fresh checkout next time
                // This ensures no stale files affect future builds
                echo "[WORKSPACE] Cleaning workspace for next build..."
                deleteDir()
                echo "[WORKSPACE] Workspace cleaned successfully"
            }
        }
        success {
            echo "[SUCCESS] Pipeline executed successfully!"
            script {
                if (env.DEPLOY_ENV == 'latest') {
                    echo "[NOTICE] Production deployment completed!"
                    // Add Slack/Email notification here if needed
                }
            }
        }
        failure {
            echo "[FAILURE] Pipeline failed!"
            // Add notification here if needed
        }
    }
}

// ================================================================================
// HELPER FUNCTION: Check if App Has Changes Between Commits
// Uses git diff to determine if a specific app directory changed
// ================================================================================
def checkAppChanges(appDir, fromCommit, toCommit) {
    try {
        // Use git diff to check if the app directory has changes between commits
        def diffOutput = bat(
            script: "@git diff --name-only ${fromCommit}...${toCommit} -- ${appDir}/ 2>nul",
            returnStdout: true
        ).trim()
        
        if (diffOutput) {
            echo "[DIFF] Files changed in ${appDir}:"
            diffOutput.split('\r?\n').each { file ->
                if (file) {
                    echo "  - ${file}"
                }
            }
            return true
        } else {
            echo "[DIFF] No changes in ${appDir} between commits"
            return false
        }
    } catch (Exception e) {
        echo "[DIFF WARNING] Could not check git diff for ${appDir}: ${e.message}"
        // If we can't determine changes, better to rebuild
        return true
    }
}