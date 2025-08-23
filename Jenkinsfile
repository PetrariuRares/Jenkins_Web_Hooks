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
        
        // Config values will be loaded from deployment-versions.yaml
        CONFIG_LOADED = 'false'
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
                    
                    // Load configuration from deployment-versions.yaml if it exists
                    if (fileExists('deployment-versions.yaml')) {
                        def deployConfig = readYaml file: 'deployment-versions.yaml'
                        
                        // Load all config values into environment
                        env.DOCKER_REGISTRY = deployConfig.config.docker_registry
                        env.DOCKER_REPO = deployConfig.config.docker_repo
                        env.DOCKER_LATEST_PATH = deployConfig.config.docker_latest_path
                        env.DOCKER_DEV_PATH = deployConfig.config.docker_dev_path
                        env.METADATA_PATH = deployConfig.config.metadata_path
                        env.BUILD_MANIFESTS_PATH = deployConfig.config.build_manifests_path
                        env.TEMP_BUILDS_PATH = deployConfig.config.temp_builds_path
                        env.DEV_RETENTION_DAYS = deployConfig.config.dev_retention_days.toString()
                        env.LATEST_VERSIONS_TO_KEEP = deployConfig.config.latest_versions_to_keep.toString()
                        
                        env.CONFIG_LOADED = 'true'
                        echo "[CONFIG] Loaded configuration from deployment-versions.yaml"
                    } else {
                        // Use default values if config file doesn't exist
                        env.DOCKER_REGISTRY = 'trialqlk1tc.jfrog.io'
                        env.DOCKER_REPO = 'dockertest-docker'
                        env.DOCKER_LATEST_PATH = 'docker-latest'
                        env.DOCKER_DEV_PATH = 'docker-dev'
                        env.METADATA_PATH = 'metadata'
                        env.BUILD_MANIFESTS_PATH = 'metadata/build-manifests'
                        env.TEMP_BUILDS_PATH = 'metadata/temporary-builds'
                        env.DEV_RETENTION_DAYS = '14'
                        env.LATEST_VERSIONS_TO_KEEP = '10'
                        
                        echo "[CONFIG] Using default configuration (deployment-versions.yaml not found)"
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
                            env.GIT_BRANCH_NAME = sh(
                                script: 'git rev-parse --abbrev-ref HEAD',
                                returnStdout: true
                            ).trim()
                            
                            if (env.GIT_BRANCH_NAME == 'HEAD') {
                                env.GIT_BRANCH_NAME = sh(
                                    script: 'git branch -r --contains HEAD | head -1',
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
                        env.GIT_COMMIT_HASH = sh(
                            script: 'git rev-parse HEAD',
                            returnStdout: true
                        ).trim()
                        env.GIT_COMMIT_SHORT = sh(
                            script: 'git rev-parse --short=8 HEAD',
                            returnStdout: true
                        ).trim()
                        env.GIT_COMMIT_MSG = sh(
                            script: 'git log -1 --pretty=%B',
                            returnStdout: true
                        ).trim()
                        env.GIT_AUTHOR = sh(
                            script: 'git log -1 --pretty=%ae',
                            returnStdout: true
                        ).trim()
                        
                        // Get previous successful commit for better change detection
                        env.GIT_PREVIOUS_COMMIT = sh(
                            script: 'git rev-parse HEAD~1 2>/dev/null || echo ""',
                            returnStdout: true
                        ).trim()
                    } catch (Exception e) {
                        env.GIT_COMMIT_HASH = "unknown"
                        env.GIT_COMMIT_SHORT = "unknown-${BUILD_NUMBER}"
                        env.GIT_COMMIT_MSG = "Unknown"
                        env.GIT_AUTHOR = "Unknown"
                        env.GIT_PREVIOUS_COMMIT = ""
                    }

                    echo "[BRANCH] ${env.GIT_BRANCH_NAME}"
                    echo "[COMMIT] ${env.GIT_COMMIT_SHORT} (${env.GIT_COMMIT_HASH})"
                    echo "[AUTHOR] ${env.GIT_AUTHOR}"
                    
                    // Reload configuration after checkout
                    if (fileExists('deployment-versions.yaml')) {
                        def deployConfig = readYaml file: 'deployment-versions.yaml'
                        
                        // Load all config values into environment
                        env.DOCKER_REGISTRY = deployConfig.config.docker_registry
                        env.DOCKER_REPO = deployConfig.config.docker_repo
                        env.DOCKER_LATEST_PATH = deployConfig.config.docker_latest_path
                        env.DOCKER_DEV_PATH = deployConfig.config.docker_dev_path
                        env.METADATA_PATH = deployConfig.config.metadata_path
                        env.BUILD_MANIFESTS_PATH = deployConfig.config.build_manifests_path
                        env.TEMP_BUILDS_PATH = deployConfig.config.temp_builds_path
                        env.DEV_RETENTION_DAYS = deployConfig.config.dev_retention_days.toString()
                        env.LATEST_VERSIONS_TO_KEEP = deployConfig.config.latest_versions_to_keep.toString()
                        
                        env.CONFIG_LOADED = 'true'
                        echo "[CONFIG] Reloaded configuration from deployment-versions.yaml"
                    }

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
        // STAGE 3: Validate Applications
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
                        dockerfiles = sh(
                            script: 'find . -name "Dockerfile" -type f 2>/dev/null || true',
                            returnStdout: true
                        ).trim()
                    } catch (Exception e) {
                        dockerfiles = ''
                    }

                    if (dockerfiles) {
                        dockerfiles.split('\n').each { file ->
                            if (file && file.trim()) {
                                def relativePath = file.replace('./', '')
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
                        sh 'echo $ARTIFACTORY_PASS | docker login $DOCKER_REGISTRY -u $ARTIFACTORY_USER --password-stdin'

                        pythonApps.each { app ->
                            def needsBuild = false
                            def reason = ""
                            
                            // For force build, always rebuild
                            if (params.FORCE_BUILD) {
                                needsBuild = true
                                reason = "Force build requested"
                            } else {
                                // Check for file changes using improved logic
                                def changedFiles = checkAppChangedFiles(app)
                                
                                // Filter out README-only changes
                                def significantChanges = changedFiles.findAll { !it.endsWith('README.md') }
                                def hasSignificantChanges = significantChanges.size() > 0

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

                                // Check if image already exists in Artifactory
                                def imageExists = sh(
                                    script: "docker pull ${imageName} > /dev/null 2>&1",
                                    returnStatus: true
                                ) == 0

                                if (imageExists) {
                                    sh "docker rmi ${imageName} 2>/dev/null || true"
                                }

                                // Simplified decision logic
                                if (hasSignificantChanges || !imageExists) {
                                    needsBuild = true
                                    reason = hasSignificantChanges ? 
                                        "Files changed (${significantChanges.size()} files)" : 
                                        "New version/tag: ${imageTag}"
                                } else {
                                    needsBuild = false
                                    reason = "No changes and image exists"
                                }
                            }
                            
                            if (needsBuild) {
                                echo "[BUILD NEEDED] ${app}: ${reason}"
                                changedApps.add(app)
                            } else {
                                echo "[SKIP] ${app}: ${reason}"
                            }
                        }
                        
                        sh "docker logout ${env.DOCKER_REGISTRY}"
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
                            
                            // Sanitize commit message for Docker label
                            def sanitizedMsg = env.GIT_COMMIT_MSG
                                .replaceAll('["\\\\]', '')
                                .replaceAll('[\r\n]+', ' ')
                                .take(100)

                            try {
                                // Build Docker image with all required labels
                                sh """
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
                                        --label "git.commit.message=${sanitizedMsg}" \
                                        --label "app.name=${app}" \
                                        -f ${app}/Dockerfile ${app}/
                                """
                                
                                // For main branch, also tag as latest
                                if (env.DEPLOY_PATH == env.DOCKER_LATEST_PATH) {
                                    sh "docker tag ${imageName}:${imageTag} ${imageName}:latest"
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
                        sh 'echo $ARTIFACTORY_PASS | docker login $DOCKER_REGISTRY -u $ARTIFACTORY_USER --password-stdin'
                        
                        def pushJobs = [:]

                        apps.each { app ->
                            pushJobs[app] = {
                                def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${env.DEPLOY_PATH}/${app}"
                                def tags = readFile("${app}_tags.txt").trim().split(',')
                                
                                tags.each { tag ->
                                    try {
                                        sh "docker push ${imageName}:${tag}"
                                        echo "[PUSH SUCCESS] ${app}: ${imageName}:${tag}"
                                    } catch (Exception e) {
                                        echo "[PUSH ERROR] ${app}:${tag}: ${e.message}"
                                        throw e
                                    }
                                }
                                
                                // Create and upload build manifest
                                createBuildManifest(app, tags[0])
                                
                                env."${app}_PUSHED_TAGS" = tags.join(',')
                            }
                        }

                        parallel pushJobs
                    }

                    sh "docker logout ${env.DOCKER_REGISTRY}"
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
                    
                    // For scheduled cleanup runs, we need to checkout first to get config
                    if (env.IS_CLEANUP_RUN == 'true' && env.CONFIG_LOADED != 'true') {
                        checkout scm
                        
                        if (fileExists('deployment-versions.yaml')) {
                            def deployConfig = readYaml file: 'deployment-versions.yaml'
                            
                            // Load all config values
                            env.DOCKER_REGISTRY = deployConfig.config.docker_registry
                            env.DOCKER_REPO = deployConfig.config.docker_repo
                            env.DOCKER_LATEST_PATH = deployConfig.config.docker_latest_path
                            env.DOCKER_DEV_PATH = deployConfig.config.docker_dev_path
                            env.METADATA_PATH = deployConfig.config.metadata_path
                            env.BUILD_MANIFESTS_PATH = deployConfig.config.build_manifests_path
                            env.TEMP_BUILDS_PATH = deployConfig.config.temp_builds_path
                            env.DEV_RETENTION_DAYS = deployConfig.config.dev_retention_days.toString()
                            env.LATEST_VERSIONS_TO_KEEP = deployConfig.config.latest_versions_to_keep.toString()
                            
                            echo "[CONFIG] Loaded configuration for cleanup"
                        }
                    }
                    
                    withCredentials([usernamePassword(
                        credentialsId: 'artifactory-credentials',
                        usernameVariable: 'ARTIFACTORY_USER',
                        passwordVariable: 'ARTIFACTORY_PASS'
                    )]) {
                        echo "[CLEANUP] Configuration:"
                        echo "  Dev retention: ${env.DEV_RETENTION_DAYS} days"
                        echo "  Latest versions to keep: ${env.LATEST_VERSIONS_TO_KEEP}"
                        echo "  Registry: ${env.DOCKER_REGISTRY}"
                        
                        // 1. Cleanup docker-dev repository
                        cleanupDevImages()
                        
                        // 2. Cleanup docker-latest repository (keep last N versions per app)
                        cleanupLatestImages()
                        
                        // 3. Cleanup metadata/temporary-builds
                        cleanupTempManifests()
                        
                        echo "[CLEANUP] Cleanup completed successfully"
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
                        sh 'rm -f *_tags.txt 2>/dev/null || true'
                        
                        // Clean up Docker images
                        if (env.APPS_TO_BUILD) {
                            def apps = env.APPS_TO_BUILD.split(',')
                            apps.each { app ->
                                def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${env.DEPLOY_PATH}/${app}"
                                
                                // Remove all tags for this app
                                sh """
                                    docker images ${imageName} -q | xargs -r docker rmi -f 2>/dev/null || true
                                """
                            }
                        }
                        
                        // Prune system
                        sh 'docker image prune -f 2>/dev/null || true'
                        sh 'docker builder prune -f --filter "until=168h" 2>/dev/null || true'
                        
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

// ================================================================================
// HELPER FUNCTIONS
// ================================================================================

// Improved change detection function
def checkAppChangedFiles(appDir) {
    try {
        def changedFiles = []
        
        // First build or no previous commit
        if (!env.GIT_PREVIOUS_COMMIT || env.GIT_PREVIOUS_COMMIT == "") {
            echo "  First build detected for ${appDir}"
            return ['first-build']
        }
        
        // Check if this is the first build by looking for previous successful build
        def lastSuccessfulCommit = sh(
            script: """
                git log --format="%H" -n 50 | while read commit; do
                    if [ "\$commit" != "${env.GIT_COMMIT_HASH}" ]; then
                        echo "\$commit"
                        break
                    fi
                done
            """,
            returnStdout: true
        ).trim()
        
        if (!lastSuccessfulCommit) {
            lastSuccessfulCommit = env.GIT_PREVIOUS_COMMIT
        }
        
        def diffOutput = sh(
            script: "git diff --name-only ${lastSuccessfulCommit}...${env.GIT_COMMIT_HASH} -- ${appDir}/ 2>/dev/null || echo ''",
            returnStdout: true
        ).trim()
        
        if (diffOutput) {
            diffOutput.split('\n').each { file ->
                if (file && file.trim()) {
                    changedFiles.add(file)
                    echo "    Changed: ${file}"
                }
            }
        }
        
        return changedFiles
    } catch (Exception e) {
        echo "  Error detecting changes: ${e.message}"
        // If we can't determine changes, return non-empty to trigger build
        return ['unknown']
    }
}

// Create and upload build manifest
def createBuildManifest(appName, version) {
    def manifestPath = env.DEPLOY_PATH == env.DOCKER_LATEST_PATH ? 
        env.BUILD_MANIFESTS_PATH : env.TEMP_BUILDS_PATH
    
    def manifest = [
        app: appName,
        version: version,
        build_number: env.BUILD_NUMBER,
        timestamp: env.TIMESTAMP,
        git_commit: env.GIT_COMMIT_HASH,
        git_branch: env.GIT_BRANCH_NAME,
        git_author: env.GIT_AUTHOR,
        jenkins_job: env.JOB_NAME,
        docker_image: "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${env.DEPLOY_PATH}/${appName}:${version}"
    ]
    
    def manifestJson = groovy.json.JsonOutput.toJson(manifest)
    def manifestFile = "${appName}-${version}-manifest.json"
    
    writeFile file: manifestFile, text: groovy.json.JsonOutput.prettyPrint(manifestJson)
    
    // Upload manifest to Artifactory
    sh """
        curl -u ${ARTIFACTORY_CREDS_USR}:${ARTIFACTORY_CREDS_PSW} \
             -T ${manifestFile} \
             "https://${DOCKER_REGISTRY}/artifactory/${DOCKER_REPO}/${manifestPath}/${appName}/${version}.json"
    """
    
    echo "[MANIFEST] Uploaded ${manifestPath}/${appName}/${version}.json"
}

// Cleanup docker-dev images older than 14 days
def cleanupDevImages() {
    echo "[CLEANUP] Cleaning docker-dev images older than ${env.DEV_RETENTION_DAYS} days..."
    
    def cutoffDate = new Date() - Integer.parseInt(env.DEV_RETENTION_DAYS)
    def cutoffTimestamp = cutoffDate.format("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'")
    
    // AQL query to find old dev images
    def aqlQuery = """
    {
        "repo": "${DOCKER_REPO}",
        "path": {"\\$match": "${DOCKER_DEV_PATH}/*"},
        "type": "folder",
        "created": {"\\$lt": "${cutoffTimestamp}"}
    }
    """
    
    def queryResult = sh(
        script: """
            curl -s -u ${ARTIFACTORY_CREDS_USR}:${ARTIFACTORY_CREDS_PSW} \
                 -X POST \
                 -H "Content-Type: text/plain" \
                 -d 'items.find(${aqlQuery})' \
                 "https://${DOCKER_REGISTRY}/artifactory/api/search/aql"
        """,
        returnStdout: true
    ).trim()
    
    // Parse results and delete old images
    def parser = new groovy.json.JsonSlurper()
    try {
        def results = parser.parseText(queryResult)
        results.results.each { item ->
            def path = "${item.repo}/${item.path}/${item.name}"
            echo "  Deleting: ${path}"
            sh """
                curl -s -u ${ARTIFACTORY_CREDS_USR}:${ARTIFACTORY_CREDS_PSW} \
                     -X DELETE \
                     "https://${DOCKER_REGISTRY}/artifactory/${path}"
            """
        }
        echo "[CLEANUP] Deleted ${results.results.size()} old dev images"
    } catch (Exception e) {
        echo "[CLEANUP] Error parsing results: ${e.message}"
    }
}

// Cleanup docker-latest images keeping only last N versions
def cleanupLatestImages() {
    echo "[CLEANUP] Cleaning docker-latest images (keeping last ${env.LATEST_VERSIONS_TO_KEEP} versions)..."
    
    // Read deployment-versions.yaml to get protected versions
    def protectedVersions = [:]
    if (fileExists('deployment-versions.yaml')) {
        def deployConfig = readYaml file: 'deployment-versions.yaml'
        deployConfig.production.each { app, version ->
            if (!protectedVersions[app]) {
                protectedVersions[app] = []
            }
            protectedVersions[app].add(version)
            echo "  Protected: ${app}:${version} (in production)"
        }
    } else {
        echo "  Warning: deployment-versions.yaml not found, no versions will be protected"
    }
    
    // Get list of all apps in docker-latest
    def appsResult = sh(
        script: """
            curl -s -u ${ARTIFACTORY_CREDS_USR}:${ARTIFACTORY_CREDS_PSW} \
                 "https://${DOCKER_REGISTRY}/artifactory/api/storage/${DOCKER_REPO}/${DOCKER_LATEST_PATH}" | \
                 python3 -c "import sys, json; data = json.load(sys.stdin); [print(child['uri'][1:]) for child in data.get('children', []) if child['folder']]"
        """,
        returnStdout: true
    ).trim()
    
    if (appsResult) {
        appsResult.split('\n').each { app ->
            echo "\n  Processing ${app}..."
            
            // Get all versions for this app
            def versionsResult = sh(
                script: """
                    curl -s -u ${ARTIFACTORY_CREDS_USR}:${ARTIFACTORY_CREDS_PSW} \
                         "https://${DOCKER_REGISTRY}/artifactory/api/docker/${DOCKER_REPO}/v2/${DOCKER_LATEST_PATH}/${app}/tags/list" | \
                         python3 -c "import sys, json; data = json.load(sys.stdin); [print(tag) for tag in data.get('tags', [])]"
                """,
                returnStdout: true
            ).trim()
            
            if (versionsResult) {
                def allVersions = versionsResult.split('\n').findAll { 
                    it && it != 'latest' && it.matches('^\\d+\\.\\d+\\.\\d+$')
                }
                
                // Sort versions properly (semantic versioning)
                allVersions = allVersions.sort { a, b ->
                    def aParts = a.split('\\.').collect { Integer.parseInt(it) }
                    def bParts = b.split('\\.').collect { Integer.parseInt(it) }
                    
                    for (int i = 0; i < 3; i++) {
                        if (aParts[i] != bParts[i]) {
                            return bParts[i] - aParts[i]  // Descending order
                        }
                    }
                    return 0
                }
                
                echo "    Found ${allVersions.size()} versions"
                
                // Determine which versions to keep
                def versionsToKeep = []
                def versionsToDelete = []
                
                allVersions.eachWithIndex { version, index ->
                    def isProtected = protectedVersions[app]?.contains(version)
                    def isRecent = index < Integer.parseInt(env.LATEST_VERSIONS_TO_KEEP)
                    
                    if (isProtected || isRecent) {
                        versionsToKeep.add(version)
                        echo "    ✓ Keep: ${version}${isProtected ? ' (protected)' : ''}"
                    } else {
                        versionsToDelete.add(version)
                        echo "    ✗ Delete: ${version}"
                    }
                }
                
                // Delete old versions
                versionsToDelete.each { version ->
                    sh """
                        curl -s -u ${ARTIFACTORY_CREDS_USR}:${ARTIFACTORY_CREDS_PSW} \
                             -X DELETE \
                             "https://${DOCKER_REGISTRY}/artifactory/${DOCKER_REPO}/${DOCKER_LATEST_PATH}/${app}/${version}"
                    """
                }
                
                if (versionsToDelete.size() > 0) {
                    echo "    Deleted ${versionsToDelete.size()} old versions"
                } else {
                    echo "    No versions to delete"
                }
            }
        }
    }
}

// Cleanup temporary build manifests older than 14 days
def cleanupTempManifests() {
    echo "[CLEANUP] Cleaning temporary build manifests older than ${env.DEV_RETENTION_DAYS} days..."
    
    def cutoffDate = new Date() - Integer.parseInt(env.DEV_RETENTION_DAYS)
    def cutoffTimestamp = cutoffDate.format("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'")
    
    // AQL query to find old manifests
    def aqlQuery = """
    {
        "repo": "${DOCKER_REPO}",
        "path": {"\\$match": "${TEMP_BUILDS_PATH}/*"},
        "type": "file",
        "name": {"\\$match": "*.json"},
        "created": {"\\$lt": "${cutoffTimestamp}"}
    }
    """
    
    def queryResult = sh(
        script: """
            curl -s -u ${ARTIFACTORY_CREDS_USR}:${ARTIFACTORY_CREDS_PSW} \
                 -X POST \
                 -H "Content-Type: text/plain" \
                 -d 'items.find(${aqlQuery})' \
                 "https://${DOCKER_REGISTRY}/artifactory/api/search/aql"
        """,
        returnStdout: true
    ).trim()
    
    // Parse results and delete old manifests
    def parser = new groovy.json.JsonSlurper()
    try {
        def results = parser.parseText(queryResult)
        results.results.each { item ->
            def path = "${item.repo}/${item.path}/${item.name}"
            echo "  Deleting manifest: ${path}"
            sh """
                curl -s -u ${ARTIFACTORY_CREDS_USR}:${ARTIFACTORY_CREDS_PSW} \
                     -X DELETE \
                     "https://${DOCKER_REGISTRY}/artifactory/${path}"
            """
        }
        echo "[CLEANUP] Deleted ${results.results.size()} old manifests"
    } catch (Exception e) {
        echo "[CLEANUP] Error parsing results: ${e.message}"
    }
}