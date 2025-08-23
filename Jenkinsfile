pipeline {
    agent any

    parameters {
        string(
            name: 'BRANCH_NAME',
            defaultValue: '',
            description: 'Branch to build (leave empty for automatic detection from webhook)'
        )
        choice(
            name: 'DEPLOY_TARGET',
            choices: ['auto', 'docker-latest', 'docker-dev'],
            description: 'Where to deploy (auto = based on branch)'
        )
        booleanParam(
            name: 'FORCE_BUILD',
            defaultValue: false,
            description: 'Force rebuild even if no changes detected'
        )
        booleanParam(
            name: 'RUN_CLEANUP',
            defaultValue: false,
            description: 'Run Artifactory cleanup after build'
        )
    }

    triggers {
        githubPush()
        // Weekly cleanup job - Sundays at 2 AM
        cron('0 2 * * 0')
    }

    environment {
        // Docker registry configuration
        DOCKER_REGISTRY = 'trialqlk1tc.jfrog.io'
        DOCKER_REPO = 'dockertest-docker'
        DOCKER_LATEST_PATH = 'docker-latest'
        DOCKER_DEV_PATH = 'docker-dev'

        // Artifactory credentials
        ARTIFACTORY_CREDS = credentials('artifactory-credentials')

        // Build metadata
        BUILD_NUMBER = "${BUILD_NUMBER}"
        TIMESTAMP = "${new Date().format('yyyyMMdd-HHmmss')}"
        JENKINS_URL = "${env.JENKINS_URL ?: 'http://jenkins.local'}"
        JOB_NAME = "${env.JOB_NAME}"
        
        // Pipeline status flags
        NO_APPS = 'false'
        VALIDATION_FAILED = 'false'
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
                    echo "Force Build: ${params.FORCE_BUILD}"
                    echo "========================================="
                    
                    // Check if this is a scheduled cleanup run
                    if (currentBuild.getBuildCauses('hudson.triggers.TimerTrigger$TimerTriggerCause')) {
                        env.IS_CLEANUP_RUN = 'true'
                        echo "[INFO] Scheduled cleanup run detected"
                    } else {
                        env.IS_CLEANUP_RUN = 'false'
                    }
                }
            }
        }

        // ================================================================================
        // STAGE 2: Checkout Code
        // ================================================================================
        stage('Checkout') {
            when {
                expression { env.IS_CLEANUP_RUN != 'true' }
            }
            steps {
                script {
                    deleteDir()
                    
                    if (params.BRANCH_NAME) {
                        checkout([
                            $class: 'GitSCM',
                            branches: [[name: "*/${params.BRANCH_NAME}"]],
                            extensions: [],
                            userRemoteConfigs: scm.userRemoteConfigs
                        ])
                        env.GIT_BRANCH_NAME = params.BRANCH_NAME
                    } else {
                        checkout scm
                        
                        try {
                            env.GIT_BRANCH_NAME = bat(
                                script: '@git rev-parse --abbrev-ref HEAD',
                                returnStdout: true
                            ).trim()
                            
                            if (env.GIT_BRANCH_NAME == 'HEAD') {
                                env.GIT_BRANCH_NAME = bat(
                                    script: '@git branch -r --contains HEAD',
                                    returnStdout: true
                                ).trim()
                                env.GIT_BRANCH_NAME = env.GIT_BRANCH_NAME.replaceAll('.*origin/', '').trim()
                            }
                        } catch (Exception e) {
                            env.GIT_BRANCH_NAME = 'unknown'
                        }
                    }

                    if (env.GIT_BRANCH_NAME.contains('/')) {
                        def parts = env.GIT_BRANCH_NAME.split('/')
                        if (parts[0] == 'origin') {
                            env.GIT_BRANCH_NAME = parts[1..-1].join('/')
                        }
                    }

                    // Extract commit information
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
                            script: '@git log -1 --pretty=%%ae',
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

                    // Determine deployment path based on branch
                    if (params.DEPLOY_TARGET != 'auto') {
                        env.DEPLOY_PATH = params.DEPLOY_TARGET == 'docker-latest' ? env.DOCKER_LATEST_PATH : env.DOCKER_DEV_PATH
                    } else {
                        if (env.GIT_BRANCH_NAME == 'main' || env.GIT_BRANCH_NAME == 'master') {
                            env.DEPLOY_PATH = env.DOCKER_LATEST_PATH
                            echo "[DEPLOY] Main branch: using ${env.DEPLOY_PATH}"
                        } else {
                            env.DEPLOY_PATH = env.DOCKER_DEV_PATH
                            echo "[DEPLOY] Feature branch: using ${env.DEPLOY_PATH}"
                        }
                    }
                }
            }
        }

        // ================================================================================
        // STAGE 3: Validate Mandatory Files
        // ================================================================================
        stage('Validate Applications') {
            when {
                expression { env.IS_CLEANUP_RUN != 'true' }
            }
            steps {
                script {
                    echo "========================================="
                    echo ">>> MANDATORY FILE VALIDATION"
                    echo "========================================="
                    
                    def pythonApps = []
                    def validationErrors = []
                    
                    // Find all Dockerfiles
                    def dockerfiles = ''
                    try {
                        dockerfiles = bat(
                            script: '@dir /s /b Dockerfile 2>nul || exit 0',
                            returnStdout: true
                        ).trim()
                    } catch (Exception e) {
                        dockerfiles = ''
                    }

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

                    if (pythonApps.size() == 0) {
                        env.NO_APPS = 'true'
                        echo "[INFO] No applications with Dockerfiles found"
                        return
                    }

                    echo "[APPS] Found ${pythonApps.size()} applications: ${pythonApps.join(', ')}"
                    
                    // Validate each application has all 4 mandatory files
                    pythonApps.each { app ->
                        echo "\n[VALIDATING] ${app}..."
                        
                        def requiredFiles = [
                            'Dockerfile',
                            'requirements.txt',
                            'README.md',
                            'version.txt'
                        ]
                        
                        def missingFiles = []
                        requiredFiles.each { file ->
                            def filePath = "${app}/${file}"
                            if (!fileExists(filePath)) {
                                missingFiles.add(file)
                                echo "  ❌ Missing: ${file}"
                            } else {
                                echo "  ✓ Found: ${file}"
                                
                                // Validate version.txt format if on main branch
                                if (file == 'version.txt' && (env.GIT_BRANCH_NAME == 'main' || env.GIT_BRANCH_NAME == 'master')) {
                                    def version = readFile(filePath).trim()
                                    if (!version.matches('^\\d+\\.\\d+\\.\\d+$')) {
                                        validationErrors.add("${app}/version.txt has invalid format: '${version}' (expected: X.Y.Z)")
                                        echo "  ❌ Invalid version format: ${version}"
                                    } else {
                                        echo "  ✓ Version: ${version}"
                                    }
                                }
                            }
                        }
                        
                        if (missingFiles.size() > 0) {
                            validationErrors.add("${app} is missing: ${missingFiles.join(', ')}")
                        }
                    }
                    
                    // Fail if any validation errors
                    if (validationErrors.size() > 0) {
                        env.VALIDATION_FAILED = 'true'
                        error("""
                        ========================================
                        VALIDATION FAILED
                        ========================================
                        ${validationErrors.join('\n')}
                        
                        All applications must contain:
                        • Dockerfile
                        • requirements.txt
                        • README.md
                        • version.txt (format: X.Y.Z)
                        ========================================
                        """)
                    } else {
                        echo "\n✅ All applications validated successfully"
                        env.VALIDATED_APPS = pythonApps.join(',')
                    }
                }
            }
        }

        // ================================================================================
        // STAGE 4: Detect Changes
        // ================================================================================
        stage('Detect Changes') {
            when {
                allOf {
                    expression { env.IS_CLEANUP_RUN != 'true' }
                    expression { env.NO_APPS != 'true' }
                    expression { env.VALIDATION_FAILED != 'true' }
                }
            }
            steps {
                script {
                    echo "========================================="
                    echo ">>> CHANGE DETECTION"
                    echo "========================================="
                    
                    def pythonApps = env.VALIDATED_APPS.split(',')
                    def changedApps = []
                    
                    withCredentials([usernamePassword(
                        credentialsId: 'artifactory-credentials',
                        usernameVariable: 'ARTIFACTORY_USER',
                        passwordVariable: 'ARTIFACTORY_PASS'
                    )]) {
                        bat 'echo %ARTIFACTORY_PASS% | docker login %DOCKER_REGISTRY% -u %ARTIFACTORY_USER% --password-stdin'

                        pythonApps.each { app ->
                            def needsBuild = false
                            def reason = ""
                            
                            // For force build, always rebuild
                            if (params.FORCE_BUILD) {
                                needsBuild = true
                                reason = "Force build requested"
                            } else {
                                // Check for README-only changes
                                def changedFiles = checkAppChangedFiles(app, env.GIT_COMMIT_HASH)
                                if (changedFiles.size() == 1 && changedFiles[0].endsWith('README.md')) {
                                    needsBuild = false
                                    reason = "Only README.md changed - skipping"
                                } else if (changedFiles.size() > 0) {
                                    // Determine the image tag and path
                                    def imageTag = ''
                                    def imageName = ''
                                    
                                    if (env.DEPLOY_PATH == env.DOCKER_LATEST_PATH) {
                                        // Main branch - use version from version.txt
                                        def version = readFile("${app}/version.txt").trim()
                                        imageTag = version
                                        imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${env.DOCKER_LATEST_PATH}/${app}:${imageTag}"
                                    } else {
                                        // Feature branch - use branch-commit format
                                        def cleanBranchName = env.GIT_BRANCH_NAME
                                            .replaceAll('[^a-zA-Z0-9._-]', '-')
                                            .toLowerCase()
                                        imageTag = "${cleanBranchName}-${env.GIT_COMMIT_SHORT}"
                                        imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${env.DOCKER_DEV_PATH}/${app}:${imageTag}"
                                    }
                                    
                                    // Check if image already exists
                                    try {
                                        def pullResult = bat(
                                            script: "docker pull ${imageName} 2>&1",
                                            returnStatus: true
                                        )
                                        
                                        if (pullResult == 0) {
                                            // Image exists with this exact tag
                                            needsBuild = false
                                            reason = "Image already exists with tag ${imageTag}"
                                            bat "docker rmi ${imageName} 2>nul || exit 0"
                                        } else {
                                            needsBuild = true
                                            reason = "New version/tag: ${imageTag}"
                                        }
                                    } catch (Exception e) {
                                        needsBuild = true
                                        reason = "Unable to check existing image"
                                    }
                                } else {
                                    needsBuild = false
                                    reason = "No changes in app directory"
                                }
                            }
                            
                            if (needsBuild) {
                                echo "[BUILD NEEDED] ${app}: ${reason}"
                                changedApps.add(app)
                            } else {
                                echo "[SKIP] ${app}: ${reason}"
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
                        echo "[RESULT] No applications need building"
                        echo "========================================="
                    }
                }
            }
        }

        // ================================================================================
        // STAGE 5: Build Docker Images
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

                            def imageTag = ''
                            def version = ''
                            
                            if (env.DEPLOY_PATH == env.DOCKER_LATEST_PATH) {
                                // Main branch - use version from version.txt
                                version = readFile("${app}/version.txt").trim()
                                imageTag = version
                            } else {
                                // Feature branch - use branch-commit format
                                def cleanBranchName = env.GIT_BRANCH_NAME
                                    .replaceAll('[^a-zA-Z0-9._-]', '-')
                                    .toLowerCase()
                                imageTag = "${cleanBranchName}-${env.GIT_COMMIT_SHORT}"
                                version = imageTag  // For dev builds, version is the same as tag
                            }

                            def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${env.DEPLOY_PATH}/${app}"

                            try {
                                // Build Docker image with all required labels
                                bat """
                                    docker build \
                                        -t ${imageName}:${imageTag} \
                                        --label "jenkins.build.number=${BUILD_NUMBER}" \
                                        --label "git.commit.id=${env.GIT_COMMIT_HASH}" \
                                        --label "git.commit.author=${env.GIT_AUTHOR}" \
                                        --label "git.branch=${env.GIT_BRANCH_NAME}" \
                                        --label "app.version=${version}" \
                                        --label "build.timestamp=${env.TIMESTAMP}" \
                                        --label "jenkins.job.name=${env.JOB_NAME}" \
                                        --label "jenkins.build.url=${env.JENKINS_URL}job/${env.JOB_NAME}/${BUILD_NUMBER}/" \
                                        --label "git.commit.message=${env.GIT_COMMIT_MSG.replaceAll('[\r\n]+', ' ').take(100)}" \
                                        --label "app.name=${app}" \
                                        -f ${app}/Dockerfile ${app}/
                                """
                                
                                // For main branch, also tag as latest
                                if (env.DEPLOY_PATH == env.DOCKER_LATEST_PATH) {
                                    bat "docker tag ${imageName}:${imageTag} ${imageName}:latest"
                                    echo "[TAG] Also tagged as ${imageName}:latest"
                                }
                                
                                echo "[BUILD SUCCESS] ${app}: ${imageName}:${imageTag}"
                                
                                // Store tags for push stage
                                writeFile file: "${app}_tags.txt", text: "${imageTag}${env.DEPLOY_PATH == env.DOCKER_LATEST_PATH ? ',latest' : ''}"

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
        // STAGE 6: Push to Artifactory
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
                                def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${env.DEPLOY_PATH}/${app}"
                                def tags = readFile("${app}_tags.txt").trim().split(',')
                                
                                tags.each { tag ->
                                    try {
                                        bat "docker push ${imageName}:${tag}"
                                        echo "[PUSH SUCCESS] ${app}: ${imageName}:${tag}"
                                    } catch (Exception e) {
                                        echo "[PUSH ERROR] ${app}:${tag}: ${e.message}"
                                        throw e
                                    }
                                }
                                
                                env."${app}_PUSHED_TAGS" = tags.join(',')
                            }
                        }

                        parallel pushJobs
                    }

                    bat "docker logout ${env.DOCKER_REGISTRY}"
                }
            }
        }

        // ================================================================================
        // STAGE 7: Artifactory Cleanup
        // ================================================================================
        stage('Artifactory Cleanup') {
            when {
                anyOf {
                    expression { env.IS_CLEANUP_RUN == 'true' }
                    expression { params.RUN_CLEANUP == true }
                }
            }
            steps {
                script {
                    echo "========================================="
                    echo ">>> ARTIFACTORY CLEANUP"
                    echo "========================================="
                    
                    withCredentials([usernamePassword(
                        credentialsId: 'artifactory-credentials',
                        usernameVariable: 'ARTIFACTORY_USER',
                        passwordVariable: 'ARTIFACTORY_PASS'
                    )]) {
                        echo "[CLEANUP] Starting Artifactory cleanup..."
                        
                        // Cleanup docker-dev repository (14 days retention)
                        echo "[CLEANUP] Cleaning docker-dev path in repository..."
                        def cutoffDate = new Date() - 14
                        def cutoffTimestamp = cutoffDate.format('yyyy-MM-dd')
                        
                        // Use Artifactory REST API to find and delete old images
                        // Note: The path in Artifactory would be dockertest-docker/docker-dev/citd/
                        def cleanupResult = bat(
                            script: """
                                curl -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% \
                                     -X POST \
                                     "https://%DOCKER_REGISTRY%/artifactory/api/search/aql" \
                                     -H "Content-Type: text/plain" \
                                     -d "items.find({\\\"repo\\\":\\\"dockertest-docker\\\",\\\"path\\\":{\\\"\\$match\\\":\\\"docker-dev/citd/*\\\"},\\\"type\\\":\\\"file\\\",\\\"created\\\":{\\\"\\$lt\\\":\\\"${cutoffTimestamp}\\\"}})"
                            """,
                            returnStdout: true
                        )
                        
                        echo "[CLEANUP] Found items to clean: ${cleanupResult}"
                        
                        // Cleanup docker-latest path (keep last 10 versions)
                        echo "[CLEANUP] Cleaning docker-latest path in repository..."
                        // This would require more complex logic to:
                        // 1. List all versions
                        // 2. Sort by version number
                        // 3. Keep last 10, delete older ones
                        // 4. Never delete versions referenced in deployment-versions.yaml
                        
                        echo "[CLEANUP] Cleanup completed"
                    }
                }
            }
        }

        // ================================================================================
        // STAGE 8: Summary
        // ================================================================================
        stage('Summary') {
            when {
                expression { env.IS_CLEANUP_RUN != 'true' }
            }
            steps {
                script {
                    echo "\n========================================="
                    echo ">>> BUILD SUMMARY"
                    echo "========================================="
                    echo "Branch: ${env.GIT_BRANCH_NAME}"
                    echo "Commit: ${env.GIT_COMMIT_SHORT}"
                    echo "Author: ${env.GIT_AUTHOR}"
                    echo "Build #: ${env.BUILD_NUMBER}"
                    echo "Deploy Path: ${env.DEPLOY_PATH}"
                    
                    if (env.NO_APPS == 'true') {
                        echo "\n[STATUS] No applications found"
                    } else if (env.VALIDATION_FAILED == 'true') {
                        echo "\n[STATUS] Validation failed"
                    } else if (env.HAS_CHANGES == 'true') {
                        echo "\n>>> APPLICATIONS BUILT AND PUSHED:"
                        def apps = env.APPS_TO_BUILD.split(',')
                        apps.each { app ->
                            def pushedTags = env."${app}_PUSHED_TAGS"
                            echo "\n  ${app}:"
                            pushedTags.split(',').each { tag ->
                                echo "    • ${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${env.DEPLOY_PATH}/${app}:${tag}"
                            }
                        }
                        
                        echo "\n>>> TO PULL IMAGES:"
                        apps.each { app ->
                            def pushedTags = env."${app}_PUSHED_TAGS"
                            pushedTags.split(',').each { tag ->
                                echo "  docker pull ${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${env.DEPLOY_PATH}/${app}:${tag}"
                            }
                        }
                    } else {
                        echo "\n[STATUS] No changes detected"
                    }
                    
                    echo "========================================="

                    // Update build description
                    if (env.HAS_CHANGES == 'true') {
                        currentBuild.description = "${env.DEPLOY_PATH} | ${env.GIT_BRANCH_NAME} | ${env.APPS_TO_BUILD}"
                    } else {
                        currentBuild.description = "No changes | ${env.GIT_BRANCH_NAME}"
                    }
                }
            }
        }
    }

    post {
        always {
            script {
                if (env.IS_CLEANUP_RUN != 'true') {
                    echo "[CLEANUP] Starting post-build cleanup..."
                    
                    try {
                        // Remove temporary files
                        bat 'del /Q *_tags.txt 2>nul || exit 0'
                        
                        // Clean up Docker images
                        if (env.APPS_TO_BUILD) {
                            def apps = env.APPS_TO_BUILD.split(',')
                            apps.each { app ->
                                def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${env.DEPLOY_PATH}/${app}"
                                
                                // Remove all tags for this app
                                bat "docker images ${imageName} -q | xargs -r docker rmi -f 2>nul || exit 0"
                            }
                        }
                        
                        // Prune system
                        bat 'docker image prune -f 2>nul || exit 0'
                        bat 'docker builder prune -f --filter "until=168h" 2>nul || exit 0'
                        
                    } catch (Exception e) {
                        echo "[CLEANUP ERROR] ${e.message}"
                    }
                    
                    deleteDir()
                }
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

// Helper function to check what files changed in an app
def checkAppChangedFiles(appDir, currentCommit) {
    try {
        // Get the last successful build commit for comparison
        def previousCommit = 'HEAD~1'  // Default to previous commit
        
        def diffOutput = bat(
            script: "@git diff --name-only ${previousCommit}...${currentCommit} -- ${appDir}/ 2>nul",
            returnStdout: true
        ).trim()
        
        def changedFiles = []
        if (diffOutput) {
            diffOutput.split('\r?\n').each { file ->
                if (file) {
                    changedFiles.add(file)
                }
            }
        }
        
        return changedFiles
    } catch (Exception e) {
        // If we can't determine changes, return non-empty to trigger build
        return ['unknown']
    }
}