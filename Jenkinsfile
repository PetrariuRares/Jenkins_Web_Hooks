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
            description: '[DEPRECATED] This parameter is ignored - builds only occur when changes are detected'
        )
        booleanParam(
            name: 'CLEANUP_OLD_SHA256',
            defaultValue: true,
            description: 'Clean up old SHA256 digests in Artifactory after pushing new images'
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
        
        // Artifactory API URL
        ARTIFACTORY_API_URL = "https://${DOCKER_REGISTRY}/artifactory/api"
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
                    echo "Cleanup Old SHA256: ${params.CLEANUP_OLD_SHA256}"
                    if (params.FORCE_BUILD) {
                        echo "[WARNING] FORCE_BUILD parameter is deprecated and ignored"
                        echo "[INFO] Builds only occur when actual changes are detected"
                    }
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
        // Calculates content hashes to determine what needs rebuilding
        // Compares with existing images in Artifactory
        // ================================================================================
        stage('Detect Changes') {
            steps {
                script {
                    echo "========================================="
                    echo ">>> CHANGE DETECTION"
                    echo "========================================="
                    echo "[DISCOVERY] Scanning for Python applications..."

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

                    // Calculate content hash for each application
                    // This hash represents the current state of the application's code
                    def appHashes = [:]
                    pythonApps.each { app ->
                        def hash = calculateAppContentHash(app)
                        appHashes[app] = hash
                        echo "[HASH] ${app}: ${hash}"
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
                                    
                                    // Store the old SHA256 digest for potential cleanup later
                                    if (params.CLEANUP_OLD_SHA256) {
                                        def oldDigest = bat(
                                            script: "@docker inspect ${imageName} --format=\"{{.RepoDigests}}\" 2>nul || echo \"\"",
                                            returnStdout: true
                                        ).trim()
                                        
                                        if (oldDigest && oldDigest.contains('@sha256:')) {
                                            def sha256Match = (oldDigest =~ /sha256:([a-f0-9]{64})/)
                                            if (sha256Match) {
                                                def oldSha256 = sha256Match[0][1]
                                                writeFile file: "${app}_old_sha256.txt", text: oldSha256
                                                echo "[SHA256 TRACKING] Stored old SHA256 for ${app}: ${oldSha256.substring(0, 12)}..."
                                            }
                                        }
                                    }

                                    if (existingHash && existingHash != currentHash) {
                                        echo "[CHANGE DETECTED] ${app}: Content changed (${existingHash} -> ${currentHash})"
                                        needsBuild = true
                                    } else if (!existingHash) {
                                        echo "[CHANGE DETECTED] ${app}: No content hash in existing image, rebuilding"
                                        needsBuild = true
                                    } else {
                                        echo "[NO CHANGE] ${app}: Content unchanged (hash: ${currentHash})"
                                    }
                                    
                                    // Clean up pulled image to save space
                                    bat "docker rmi ${imageName} 2>nul || exit 0"
                                } else {
                                    echo "[NEW IMAGE] ${app}: Image doesn't exist in registry"
                                    needsBuild = true
                                }
                            } catch (Exception e) {
                                echo "[NEW IMAGE] ${app}: Unable to check existing image, will build"
                                needsBuild = true
                            }

                            // Only add to build list if actual changes detected
                            // FORCE_BUILD is intentionally ignored here
                            if (needsBuild) {
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
                    echo "========================================="
                    echo ">>> DOCKER BUILD"
                    echo "========================================="

                    def apps = env.APPS_TO_BUILD.split(',')
                    def buildJobs = [:]

                    // Create parallel build jobs for each application
                    apps.each { app ->
                        buildJobs[app] = {
                            echo "[BUILD START] ${app}"

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
                                
                                echo "[BUILD SUCCESS] ${app}: ${imageName}:${imageTag} (hash: ${contentHash})"
                                
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
        // STAGE 5: Push to Artifactory with SHA256 Cleanup
        // Pushes built images to JFrog Artifactory
        // Captures new SHA256 digests and removes old ones if enabled
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
                    def sha256Cleanup = [:]

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
                                    
                                    // Get the new SHA256 digest after push
                                    def newDigest = bat(
                                        script: "@docker inspect ${imageName}:${imageTag} --format=\"{{.RepoDigests}}\" 2>nul || echo \"\"",
                                        returnStdout: true
                                    ).trim()
                                    
                                    if (newDigest && newDigest.contains('@sha256:')) {
                                        def sha256Match = (newDigest =~ /sha256:([a-f0-9]{64})/)
                                        if (sha256Match) {
                                            def newSha256 = sha256Match[0][1]
                                            writeFile file: "${app}_new_sha256.txt", text: newSha256
                                            echo "[SHA256] New digest for ${app}: ${newSha256.substring(0, 12)}..."
                                            
                                            // Schedule cleanup if old SHA256 exists and is different
                                            if (params.CLEANUP_OLD_SHA256 && fileExists("${app}_old_sha256.txt")) {
                                                def oldSha256 = readFile("${app}_old_sha256.txt").trim()
                                                if (oldSha256 && oldSha256 != newSha256) {
                                                    sha256Cleanup[app] = [old: oldSha256, new: newSha256]
                                                    echo "[SHA256 CLEANUP] Scheduled cleanup for ${app}: old ${oldSha256.substring(0, 12)}..."
                                                }
                                            }
                                        }
                                    }
                                    
                                } catch (Exception e) {
                                    echo "[PUSH ERROR] ${app}: ${e.message}"
                                    throw e
                                }
                            }
                        }

                        // Execute all push jobs in parallel
                        parallel pushJobs
                        
                        // Perform SHA256 cleanup after successful pushes
                        if (params.CLEANUP_OLD_SHA256 && sha256Cleanup.size() > 0) {
                            echo "========================================="
                            echo ">>> SHA256 CLEANUP"
                            echo "========================================="
                            
                            sha256Cleanup.each { app, digests ->
                                try {
                                    echo "[SHA256 CLEANUP] Processing ${app}..."
                                    echo "  Old SHA256: ${digests.old.substring(0, 12)}..."
                                    echo "  New SHA256: ${digests.new.substring(0, 12)}..."
                                    
                                    // Use Artifactory REST API to delete old SHA256
                                    def deleteUrl = "${env.ARTIFACTORY_API_URL}/docker/${env.DOCKER_REPO}/v2/${app}/manifests/sha256:${digests.old}"
                                    
                                    def deleteResult = bat(
                                        script: """
                                            @curl -X DELETE \
                                                -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% \
                                                -H "Accept: application/vnd.docker.distribution.manifest.v2+json" \
                                                "${deleteUrl}" \
                                                -w "\\n%%{http_code}" \
                                                -o delete_response.txt \
                                                -s
                                        """,
                                        returnStdout: true
                                    ).trim()
                                    
                                    def httpCode = deleteResult.split('\n')[-1]
                                    
                                    if (httpCode == '200' || httpCode == '202' || httpCode == '204') {
                                        echo "[SHA256 CLEANUP SUCCESS] ${app}: Removed old SHA256 ${digests.old.substring(0, 12)}..."
                                    } else if (httpCode == '404') {
                                        echo "[SHA256 CLEANUP INFO] ${app}: Old SHA256 already removed or not found"
                                    } else {
                                        echo "[SHA256 CLEANUP WARNING] ${app}: Unexpected response code ${httpCode}"
                                        if (fileExists('delete_response.txt')) {
                                            def response = readFile('delete_response.txt')
                                            echo "  Response: ${response}"
                                        }
                                    }
                                    
                                    // Clean up response file
                                    bat 'del /Q delete_response.txt 2>nul || exit 0'
                                    
                                } catch (Exception e) {
                                    echo "[SHA256 CLEANUP ERROR] ${app}: ${e.message}"
                                    echo "[SHA256 CLEANUP] Continuing despite error..."
                                }
                            }
                            
                            echo "========================================="
                            echo "[SHA256 CLEANUP] Cleanup process completed"
                            echo "========================================="
                        }
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
                        // Remove temporary tag and hash files
                        bat 'del /Q *_tag.txt 2>nul || exit 0'
                        bat 'del /Q *_hash.txt 2>nul || exit 0'
                        bat 'del /Q *_old_sha256.txt 2>nul || exit 0'
                        bat 'del /Q *_new_sha256.txt 2>nul || exit 0'
                        bat 'del /Q delete_response.txt 2>nul || exit 0'
                        
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
                    echo "Commit: ${env.GIT_COMMIT_HASH}"
                    echo "Author: ${env.GIT_AUTHOR}"
                    echo "Build #: ${env.BUILD_NUMBER}"
                    echo "Target: ${env.DEPLOY_ENV}"
                    echo "SHA256 Cleanup: ${params.CLEANUP_OLD_SHA256 ? 'Enabled' : 'Disabled'}"
                    
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
                            
                            // Show new SHA256 if available
                            if (fileExists("${app}_new_sha256.txt")) {
                                def newSha256 = readFile("${app}_new_sha256.txt").trim()
                                echo "    SHA256: ${newSha256.substring(0, 12)}..."
                            }
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
            echo "[PIPELINE] Completed"
            
            script {
                echo "[DOCKER CLEANUP] Starting Docker cleanup..."
                
                try {
                    // Remove temporary files
                    echo "[DOCKER CLEANUP] Removing temporary files..."
                    bat 'del /Q *_tag.txt 2>nul || exit 0'
                    bat 'del /Q *_hash.txt 2>nul || exit 0'
                    bat 'del /Q *_old_sha256.txt 2>nul || exit 0'
                    bat 'del /Q *_new_sha256.txt 2>nul || exit 0'
                    bat 'del /Q delete_response.txt 2>nul || exit 0'
                    
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
// HELPER FUNCTION: Calculate Content Hash
// Creates a hash representing the current state of an application
// Used to determine if Docker image needs rebuilding
// Dynamically scans all files in the application directory
// ================================================================================
def calculateAppContentHash(appDir) {
    try {
        def combinedContent = ''
        def fileMap = [:] // Map to store file paths and their hashes for consistent ordering
        
        // Read .dockerignore patterns if exists
        def dockerignorePath = "${appDir}/.dockerignore"
        def ignorePatterns = getDockerignorePatterns(dockerignorePath)
        
        // Add default ignore patterns (always skip these)
        def defaultIgnores = ['.git', '.svn', '.hg', 'node_modules', '__pycache__', '.pytest_cache', '.tox', '*.pyc', '*.pyo', '*.pyd', '.DS_Store', 'Thumbs.db']
        ignorePatterns.addAll(defaultIgnores)
        
        echo "[HASH] Calculating content hash for ${appDir}..."
        echo "[HASH] Active ignore patterns: ${ignorePatterns.size()} patterns loaded"
        
        // Get all files recursively using Windows dir command
        def allFiles = bat(
            script: "@dir /s /b /a:-d \"${appDir}\" 2>nul || exit 0",
            returnStdout: true
        ).trim()
        
        if (allFiles) {
            def fileCount = 0
            def skippedCount = 0
            
            allFiles.split('\r?\n').each { fullPath ->
                if (fullPath && fullPath.trim()) {
                    // Get relative path from app directory
                    def relativePath = fullPath.replace(env.WORKSPACE + '\\', '')
                        .replace('\\', '/')
                        .replace(appDir + '/', '')
                    
                    // Skip if file should be ignored
                    if (shouldIgnoreFile(relativePath, ignorePatterns)) {
                        skippedCount++
                        return // continue to next file
                    }
                    
                    // Skip binary files and large files
                    if (isBinaryOrLargeFile(fullPath)) {
                        skippedCount++
                        return // continue to next file
                    }
                    
                    try {
                        // Read file content and calculate hash
                        def content = readFile(fullPath)
                        def fileHash = content.hashCode().toString()
                        
                        // Store in map for consistent ordering
                        fileMap[relativePath] = fileHash
                        fileCount++
                        
                    } catch (Exception e) {
                        // Skip files that can't be read (permissions, binary, etc.)
                        skippedCount++
                    }
                }
            }
            
            echo "[HASH] Processed ${fileCount} files, skipped ${skippedCount} files"
            
            // Build combined content string in sorted order for consistency
            fileMap.keySet().sort().each { path ->
                combinedContent += "${path}:${fileMap[path]};"
            }
        }
        
        // Return hash of combined content
        if (combinedContent) {
            def finalHash = combinedContent.hashCode().toString()
            echo "[HASH] Final hash for ${appDir}: ${finalHash}"
            return finalHash
        } else {
            echo "[HASH] No files found to hash in ${appDir}, using timestamp"
            return new Date().getTime().toString()
        }
        
    } catch (Exception e) {
        echo "[HASH ERROR] Could not calculate hash for ${appDir}: ${e.message}"
        // Return timestamp as fallback to ensure build happens
        return new Date().getTime().toString()
    }
}

// Helper function to parse .dockerignore patterns
def getDockerignorePatterns(dockerignorePath) {
    def patterns = []
    
    if (fileExists(dockerignorePath)) {
        try {
            def dockerignore = readFile(dockerignorePath)
            dockerignore.split('\n').each { line ->
                line = line.trim()
                // Skip empty lines and comments
                if (line && !line.startsWith('#')) {
                    // Convert dockerignore patterns to simple patterns we can match
                    // Remove leading slash if present
                    if (line.startsWith('/')) {
                        line = line.substring(1)
                    }
                    patterns.add(line)
                }
            }
        } catch (Exception e) {
            echo "[HASH] Could not read .dockerignore: ${e.message}"
        }
    }
    
    return patterns
}

// Helper function to check if a file should be ignored
def shouldIgnoreFile(relativePath, ignorePatterns) {
    def pathToCheck = relativePath.toLowerCase()
    
    for (pattern in ignorePatterns) {
        def patternLower = pattern.toLowerCase()
        
        // Handle different pattern types
        if (patternLower.contains('*')) {
            // Wildcard pattern
            def regexPattern = patternLower
                .replace('.', '\\.')
                .replace('**/', '.*')
                .replace('*', '[^/]*')
                .replace('?', '.')
            
            if (pathToCheck.matches(".*${regexPattern}.*")) {
                return true
            }
        } else if (patternLower.startsWith('.')) {
            // File extension pattern
            if (pathToCheck.endsWith(patternLower)) {
                return true
            }
        } else {
            // Direct match or directory match
            if (pathToCheck.contains(patternLower)) {
                return true
            }
        }
    }
    
    return false
}

// Helper function to detect binary or large files that shouldn't be hashed
def isBinaryOrLargeFile(filePath) {
    try {
        // Check file size first (skip files larger than 10MB)
        def file = new File(filePath)
        if (file.length() > 10 * 1024 * 1024) {
            return true
        }
        
        // Check for common binary extensions
        def binaryExtensions = [
            '.exe', '.dll', '.so', '.dylib', '.bin', '.dat',
            '.zip', '.tar', '.gz', '.7z', '.rar',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg',
            '.mp3', '.mp4', '.avi', '.mov', '.wav',
            '.pdf', '.doc', '.docx', '.xls', '.xlsx',
            '.pyc', '.pyo', '.pyd', '.class', '.jar', '.war',
            '.db', '.sqlite', '.sqlite3'
        ]
        
        def fileName = filePath.toLowerCase()
        for (ext in binaryExtensions) {
            if (fileName.endsWith(ext)) {
                return true
            }
        }
        
        return false
    } catch (Exception e) {
        // If we can't check, assume it's okay to process
        return false
    }
}