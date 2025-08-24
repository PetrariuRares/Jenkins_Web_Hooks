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
            description: 'Run FULL cleanup (docker-latest + metadata). Note: docker-dev cleanup always runs automatically.'
        )
        string(
            name: 'CLEANUP_BRANCH',
            defaultValue: '',
            description: 'Specific branch to clean up (e.g., after merging). Leave empty for full cleanup.'
        )
        booleanParam(
            name: 'DRY_RUN_CLEANUP',
            defaultValue: false,
            description: 'Preview cleanup actions without actually deleting (shows what would be removed)'
        )

        string(
            name: 'FORCE_DELETE_APP',
            defaultValue: '',
            description: 'Force delete entire app folder from docker-dev (e.g., "app1"). Use with caution!'
        )
        string(
            name: 'SLACK_WEBHOOK_URL',
            defaultValue: '',
            description: 'Slack webhook URL for notifications (optional)'
        )
        booleanParam(
            name: 'NOTIFY_ON_SUCCESS',
            defaultValue: false,
            description: 'Send notifications on successful builds (default: failures only)'
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
                    echo "Full Cleanup: ${params.RUN_CLEANUP}"
                    echo "Cleanup Branch: ${params.CLEANUP_BRANCH ?: 'none'}"
                    echo "Force Delete App: ${params.FORCE_DELETE_APP ?: 'none'}"
                    echo "Dry Run Cleanup: ${params.DRY_RUN_CLEANUP}"
                    echo "Auto Cleanup: ENABLED (default behavior)"
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
                        
                        // Get previous successful commit for better change detection
                        env.GIT_PREVIOUS_COMMIT = bat(
                            script: '@git rev-parse HEAD~1 2>nul || echo ""',
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
                    
                    // Find all Dockerfiles using Windows commands
                    def dockerfiles = ''
                    try {
                        dockerfiles = bat(
                            script: '@dir /s /b Dockerfile 2>nul || echo ""',
                            returnStdout: true
                        ).trim()
                    } catch (Exception e) {
                        dockerfiles = ''
                    }

                    if (dockerfiles) {
                        dockerfiles.split('\r?\n').each { file ->
                            if (file && file.trim() && file.contains('Dockerfile')) {
                                // Convert Windows path to relative path
                                def relativePath = file.replace(env.WORKSPACE + '\\', '').replace('\\', '/')
                                def parts = relativePath.split('/')
                                
                                // Check if Dockerfile is in a subdirectory (not root)
                                if (parts.length == 2 && parts[1] == 'Dockerfile') {
                                    def appName = parts[0]
                                    // Exclude hidden directories and jenkins directories
                                    if (!appName.startsWith('.') && !appName.startsWith('@')) {
                                        pythonApps.add(appName)
                                        echo "[FOUND] Application: ${appName}"
                                    }
                                }
                            }
                        }
                    }

                    if (pythonApps.size() == 0) {
                        env.NO_APPS = 'true'
                        env.VALIDATED_APPS = ''  // Set empty string to avoid null
                        echo "[INFO] No applications with Dockerfiles found"
                        echo "[DEBUG] Searched in: ${env.WORKSPACE}"
                        echo "[DEBUG] Raw output: ${dockerfiles}"
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
        // STAGE 4: Detect Changes (FIXED FOR FEATURE BRANCHES)
        // ================================================================================
        stage('Detect Changes') {
            when {
                allOf {
                    expression { env.IS_CLEANUP_RUN != 'true' }
                    expression { env.NO_APPS != 'true' }
                    expression { env.VALIDATION_FAILED != 'true' }
                    expression { env.VALIDATED_APPS != null && env.VALIDATED_APPS != '' }
                }
            }
            steps {
                script {
                    echo "========================================="
                    echo ">>> CHANGE DETECTION"
                    echo "========================================="
                    
                    def pythonApps = env.VALIDATED_APPS.split(',')
                    def changedApps = []
                    
                    // Determine if this is main branch
                    def isMainBranch = (env.GIT_BRANCH_NAME == 'main' || env.GIT_BRANCH_NAME == 'master')
                    echo "[INFO] Branch type: ${isMainBranch ? 'MAIN BRANCH' : 'FEATURE BRANCH'}"
                    echo "[INFO] Branch name: ${env.GIT_BRANCH_NAME}"
                    echo "[INFO] Detection strategy: ${isMainBranch ? 'Build if changed OR new version' : 'Build ONLY if changed'}"
                    echo ""
                    
                    withCredentials([usernamePassword(
                        credentialsId: 'artifactory-credentials',
                        usernameVariable: 'ARTIFACTORY_USER',
                        passwordVariable: 'ARTIFACTORY_PASS'
                    )]) {
                        bat "echo %ARTIFACTORY_PASS% | docker login %DOCKER_REGISTRY% -u %ARTIFACTORY_USER% --password-stdin"

                        pythonApps.each { app ->
                            def needsBuild = false
                            def reason = ""
                            
                            echo "[ANALYZING] ${app}..."
                            echo "  Current commit: ${env.GIT_COMMIT_SHORT}"
                            echo "  Previous commit: ${env.GIT_PREVIOUS_COMMIT ?: 'none'}"

                            // For force build, always rebuild
                            if (params.FORCE_BUILD) {
                                needsBuild = true
                                reason = "Force build requested by user"
                            } else {
                                // Check for file changes using enhanced function
                                def changeResult = checkAppChangedFiles(app)
                                def changedFiles = changeResult.files ?: []
                                def detectionMethod = changeResult.method ?: "unknown"
                                def isFirstBuild = changeResult.firstBuild ?: false

                                echo "  Detection method: ${detectionMethod}"
                                if (changeResult.error) {
                                    echo "  Detection error: ${changeResult.error}"
                                }

                                // Filter out README-only changes
                                def significantChanges = changedFiles.findAll { !it.endsWith('README.md') }
                                def hasSignificantChanges = significantChanges.size() > 0

                                // Show what changed
                                if (hasSignificantChanges) {
                                    echo "  📝 Files changed in ${app} (${significantChanges.size()} significant):"
                                    significantChanges.each { file ->
                                        echo "    - ${file}"
                                    }
                                } else if (changedFiles.size() > 0) {
                                    echo "  📝 Only README changes in ${app} (${changedFiles.size()} total files)"
                                } else {
                                    echo "  ✅ No changes detected in ${app}"
                                }

                                // Determine the image tag
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

                                echo "  Image tag: ${imageTag}"

                                // Check if image already exists in Artifactory
                                def imageExists = bat(
                                    script: "docker pull ${imageName} >nul 2>&1",
                                    returnStatus: true
                                ) == 0

                                if (imageExists) {
                                    echo "  Image exists: YES"
                                    bat "docker rmi ${imageName} 2>nul || exit 0"
                                } else {
                                    echo "  Image exists: NO"
                                }

                                // ===== IMPROVED DECISION LOGIC =====
                                if (isMainBranch) {
                                    // MAIN BRANCH: Build if files changed OR image doesn't exist (new version)
                                    if (hasSignificantChanges) {
                                        needsBuild = true
                                        reason = "Files changed (${significantChanges.size()} files modified)"
                                    } else if (!imageExists) {
                                        needsBuild = true
                                        reason = "New version ${imageTag} needs to be built"
                                    } else {
                                        needsBuild = false
                                        reason = "No changes and image already exists"
                                    }
                                } else {
                                    // FEATURE BRANCH: Build if files changed AND image doesn't exist
                                    // This prevents rebuilding the same commit multiple times
                                    if (imageExists) {
                                        needsBuild = false
                                        reason = "Image already exists for this commit - skipping rebuild"
                                    } else if (hasSignificantChanges) {
                                        needsBuild = true
                                        reason = "Files changed and image doesn't exist (${significantChanges.size()} files modified)"
                                    } else {
                                        needsBuild = false
                                        reason = "No changes in ${app} - skipping build on feature branch"
                                    }
                                }
                            }
                            
                            // Final decision
                            if (needsBuild) {
                                echo "  ✓ [BUILD NEEDED] ${app}: ${reason}"
                                changedApps.add(app)
                            } else {
                                echo "  ✗ [SKIP] ${app}: ${reason}"
                            }
                            echo ""
                        }
                        
                        bat "docker logout ${env.DOCKER_REGISTRY}"
                    }
                    
                    // Summary
                    echo "========================================="
                    if (changedApps.size() > 0) {
                        env.APPS_TO_BUILD = changedApps.join(',')
                        env.HAS_CHANGES = 'true'
                        echo "[RESULT] Will build ${changedApps.size()} app(s): ${env.APPS_TO_BUILD}"
                    } else {
                        env.HAS_CHANGES = 'false'
                        echo "[RESULT] No applications need building"
                    }
                    echo "========================================="
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
                                // Build Docker image with all required labels (Windows compatible)
                                def buildCommand = """docker build -t ${imageName}:${imageTag} ^
                                    --label "jenkins.build.number=${BUILD_NUMBER}" ^
                                    --label "git.commit.id=${env.GIT_COMMIT_HASH}" ^
                                    --label "git.commit.author=${env.GIT_AUTHOR}" ^
                                    --label "git.branch=${env.GIT_BRANCH_NAME}" ^
                                    --label "app.version=${version}" ^
                                    --label "build.timestamp=${env.TIMESTAMP}" ^
                                    --label "jenkins.job.name=${env.JOB_NAME}" ^
                                    --label "jenkins.build.url=${env.JENKINS_URL}job/${env.JOB_NAME}/${BUILD_NUMBER}/" ^
                                    --label "app.name=${app}" ^
                                    -f ${app}/Dockerfile ${app}/"""
                                    
                                bat buildCommand.replaceAll('\n', ' ')
                                
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
                        bat "echo %ARTIFACTORY_PASS% | docker login %DOCKER_REGISTRY% -u %ARTIFACTORY_USER% --password-stdin"
                        
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
                                
                                // Create and upload build manifest
                                createBuildManifest(app, tags[0])
                                
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
                // Always run cleanup, unless it's a validation failure
                not {
                    expression { env.VALIDATION_FAILED == 'true' }
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
                        echo "  Dry Run Mode: ${params.DRY_RUN_CLEANUP}"
                        
                        if (params.FORCE_DELETE_APP != '') {
                            // Force delete entire app folder
                            echo "[CLEANUP] Force deleting entire app: ${params.FORCE_DELETE_APP}"
                            forceDeleteApp(params.FORCE_DELETE_APP)
                        } else if (params.CLEANUP_BRANCH != '') {
                            // Clean up specific branch
                            echo "[CLEANUP] Cleaning up specific branch: ${params.CLEANUP_BRANCH}"
                            cleanupSpecificBranch(params.CLEANUP_BRANCH)
                        } else if (env.IS_CLEANUP_RUN == 'true') {
                            // Scheduled full cleanup (weekly)
                            echo "[CLEANUP] Running scheduled full cleanup"
                            // 1. Cleanup docker-dev repository (branch-aware + time-based)
                            cleanupDevImages()

                            // 2. Cleanup docker-latest repository (keep last N versions per app)
                            cleanupLatestImages()

                            // 3. Cleanup metadata/temporary-builds
                            cleanupTempManifests()
                        } else {
                            // Default automatic cleanup - runs on every build
                            echo "[CLEANUP] Running automatic cleanup (default behavior)"
                            echo "[CLEANUP] This will remove images from deleted branches and clean up orphaned storage"

                            // Always clean up docker-dev repository (orphaned branches)
                            cleanupDevImages()

                            // Only run full cleanup if explicitly requested
                            if (params.RUN_CLEANUP == true) {
                                echo "[CLEANUP] Full cleanup requested - also cleaning docker-latest and metadata"
                                cleanupLatestImages()
                                cleanupTempManifests()
                            }
                        }
                        
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
                        echo "Make sure you have application folders with:"
                        echo "  - Dockerfile"
                        echo "  - requirements.txt"
                        echo "  - README.md"
                        echo "  - version.txt"
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

                    echo "\n>>> AUTOMATIC CLEANUP:"
                    echo "  • Docker-dev cleanup: ALWAYS RUNS (removes orphaned branches)"
                    echo "  • Storage cleanup: ALWAYS RUNS (removes sha256, _uploads, etc.)"
                    echo "  • Garbage collection: ALWAYS TRIGGERED (reclaims storage space)"
                    if (params.RUN_CLEANUP) {
                        echo "  • Full cleanup: ENABLED (docker-latest + metadata)"
                    } else {
                        echo "  • Full cleanup: DISABLED (use RUN_CLEANUP=true to enable)"
                    }

                    echo "========================================="

                    // Update build description
                    if (env.HAS_CHANGES == 'true') {
                        currentBuild.description = "${env.DEPLOY_PATH} | ${env.GIT_BRANCH_NAME} | ${env.APPS_TO_BUILD}"
                    } else if (env.NO_APPS == 'true') {
                        currentBuild.description = "No apps found | ${env.GIT_BRANCH_NAME}"
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
                        // Remove temporary files (Windows)
                        bat "del /Q *_tags.txt 2>nul || exit 0"
                        
                        // Clean up Docker images
                        if (env.APPS_TO_BUILD) {
                            def apps = env.APPS_TO_BUILD.split(',')
                            apps.each { app ->
                                def imageName = "${env.DOCKER_REGISTRY}/${env.DOCKER_REPO}/${env.DEPLOY_PATH}/${app}"
                                
                                // Remove all tags for this app (Windows)
                                bat """
                                    for /f "tokens=*" %%i in ('docker images ${imageName} -q 2^>nul') do docker rmi -f %%i 2>nul || exit 0
                                """
                            }
                        }
                        
                        // Prune system
                        bat "docker image prune -f 2>nul || exit 0"
                        bat "docker builder prune -f --filter \"until=168h\" 2>nul || exit 0"
                        
                    } catch (Exception e) {
                        echo "[CLEANUP ERROR] ${e.message}"
                    }
                    
                    deleteDir()
                }
            }
        }
        success {
            script {
                echo "[SUCCESS] Pipeline executed successfully!"

                def successMessage = "Build completed successfully"
                def details = ""

                if (env.HAS_CHANGES == 'true') {
                    def apps = env.APPS_TO_BUILD?.split(',') ?: []
                    details = "Built ${apps.size()} app(s): ${apps.join(', ')}"
                } else {
                    details = "No changes detected - cleanup performed"
                }

                if (params.NOTIFY_ON_SUCCESS) {
                    sendNotification('SUCCESS', successMessage, details)
                }
            }
        }
        failure {
            script {
                echo "[FAILURE] Pipeline failed!"

                def failureReason = "Build failed"
                if (env.VALIDATION_FAILED == 'true') {
                    failureReason = "Application validation failed"
                } else if (env.NO_APPS == 'true') {
                    failureReason = "No applications found"
                }

                sendNotification('FAILURE', failureReason, "Check build logs for details")
            }
        }
    }
}

// ================================================================================
// HELPER FUNCTIONS
// ================================================================================

// Robust HTTP call with retry logic and proper error handling
def makeHttpCall(url, method = 'GET', maxRetries = 3, retryDelay = 5) {
    def attempt = 0
    def lastError = null

    while (attempt < maxRetries) {
        attempt++
        try {
            echo "    🌐 HTTP ${method} attempt ${attempt}/${maxRetries}: ${url}"

            def curlCommand = method == 'DELETE' ?
                "@curl -s -w \"HTTPSTATUS:%{http_code}\" -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% -X ${method} \"${url}\"" :
                "@curl -s -w \"HTTPSTATUS:%{http_code}\" -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% \"${url}\""

            def response = bat(
                script: curlCommand,
                returnStdout: true
            ).trim()

            def httpStatus = response.contains('HTTPSTATUS:') ?
                response.split('HTTPSTATUS:')[1] : '000'
            def responseBody = response.contains('HTTPSTATUS:') ?
                response.split('HTTPSTATUS:')[0] : response

            // Check if this is a successful response
            if (httpStatus.startsWith('2') || httpStatus == '404') {
                echo "    ✅ HTTP ${method} success: ${httpStatus}"
                return [
                    success: true,
                    httpStatus: httpStatus,
                    response: responseBody,
                    attempt: attempt
                ]
            } else if (httpStatus.startsWith('5') && attempt < maxRetries) {
                // Server error - retry
                echo "    ⚠ HTTP ${method} server error: ${httpStatus} - retrying in ${retryDelay}s"
                sleep(retryDelay)
                lastError = "HTTP ${httpStatus}: ${responseBody}"
                continue
            } else {
                // Client error or final attempt - don't retry
                echo "    ❌ HTTP ${method} failed: ${httpStatus}"
                return [
                    success: false,
                    httpStatus: httpStatus,
                    response: responseBody,
                    attempt: attempt,
                    error: "HTTP ${httpStatus}: ${responseBody}"
                ]
            }
        } catch (Exception e) {
            lastError = e.message
            echo "    ❌ HTTP ${method} exception on attempt ${attempt}: ${e.message}"

            if (attempt < maxRetries) {
                echo "    ⏳ Retrying in ${retryDelay} seconds..."
                sleep(retryDelay)
            }
        }
    }

    // All attempts failed
    return [
        success: false,
        httpStatus: '000',
        response: '',
        attempt: attempt,
        error: "All ${maxRetries} attempts failed. Last error: ${lastError}"
    ]
}

// Send notifications (Slack, email, etc.)
def sendNotification(status, message, details = '') {
    try {
        def color = status == 'SUCCESS' ? 'good' : (status == 'FAILURE' ? 'danger' : 'warning')
        def emoji = status == 'SUCCESS' ? '✅' : (status == 'FAILURE' ? '❌' : '⚠️')

        def buildUrl = "${env.JENKINS_URL}job/${env.JOB_NAME}/${BUILD_NUMBER}/"
        def gitInfo = "${env.GIT_BRANCH_NAME} (${env.GIT_COMMIT_SHORT})"

        def slackMessage = """
${emoji} *Jenkins Build ${status}*
*Job:* ${env.JOB_NAME} #${BUILD_NUMBER}
*Branch:* ${gitInfo}
*Message:* ${message}
${details ? "*Details:* ${details}" : ""}
*Build URL:* ${buildUrl}
        """.trim()

        // Send Slack notification if webhook URL is provided
        if (params.SLACK_WEBHOOK_URL && params.SLACK_WEBHOOK_URL.trim()) {
            echo "📢 Sending Slack notification: ${status}"

            def payload = groovy.json.JsonOutput.toJson([
                text: slackMessage,
                color: color,
                username: "Jenkins CI/CD",
                icon_emoji: ":jenkins:"
            ])

            bat """
                @curl -s -X POST -H "Content-type: application/json" ^
                     --data "${payload.replace('"', '\\"')}" ^
                     "${params.SLACK_WEBHOOK_URL}" || echo "Slack notification failed"
            """
        }

        // Log notification for debugging
        echo "📢 Notification sent: ${status} - ${message}"

    } catch (Exception e) {
        echo "⚠️ Failed to send notification: ${e.message}"
    }
}

// Enhanced change detection function with multiple strategies
def checkAppChangedFiles(appDir) {
    try {
        def changedFiles = []
        def changeDetectionMethod = "unknown"

        echo "    🔍 Detecting changes for ${appDir}..."

        // Method 1: Jenkins changeset information (most reliable for webhooks)
        if (currentBuild.changeSets && currentBuild.changeSets.size() > 0) {
            echo "    📋 Using Jenkins changeset information"
            changeDetectionMethod = "jenkins-changeset"

            currentBuild.changeSets.each { changeSet ->
                changeSet.items.each { change ->
                    change.affectedFiles.each { file ->
                        if (file.path.startsWith("${appDir}/")) {
                            changedFiles.add(file.path)
                            echo "      📄 Changed: ${file.path} (${file.editType})"
                        }
                    }
                }
            }

            if (changedFiles.size() > 0) {
                echo "    ✅ Found ${changedFiles.size()} changed files via Jenkins changeset"
                return [files: changedFiles, method: changeDetectionMethod]
            }
        }

        // Method 2: Git diff with improved commit detection
        def compareCommit = env.GIT_PREVIOUS_COMMIT
        if (!compareCommit || compareCommit == "") {
            // Try to get the previous commit from the same branch
            try {
                compareCommit = bat(
                    script: "@git rev-parse HEAD~1 2>nul || echo \"\"",
                    returnStdout: true
                ).trim()
                echo "    📍 Using HEAD~1 as comparison: ${compareCommit}"
            } catch (Exception e) {
                echo "    ⚠ Could not determine previous commit: ${e.message}"
            }
        }

        if (compareCommit && compareCommit != "") {
            echo "    🔄 Comparing ${compareCommit}...HEAD for ${appDir}/"
            changeDetectionMethod = "git-diff"

            def diffOutput = bat(
                script: "@git diff --name-only ${compareCommit}...HEAD -- ${appDir}/ 2>nul || echo \"\"",
                returnStdout: true
            ).trim()

            if (diffOutput) {
                diffOutput.split('\r?\n').each { file ->
                    if (file && file.trim()) {
                        changedFiles.add(file)
                        echo "      📄 Changed: ${file}"
                    }
                }
            }

            if (changedFiles.size() > 0) {
                echo "    ✅ Found ${changedFiles.size()} changed files via git diff"
                return [files: changedFiles, method: changeDetectionMethod]
            } else {
                echo "    ✅ No files changed since ${compareCommit}"
                return [files: [], method: changeDetectionMethod]
            }
        }

        // Method 3: Check if this is a completely new app (no previous builds)
        echo "    🆕 First build or no previous commit - checking if app exists in registry"
        changeDetectionMethod = "first-build"

        // Return empty files but indicate this is a first build
        return [files: [], method: changeDetectionMethod, firstBuild: true]

    } catch (Exception e) {
        echo "    ❌ Error detecting changes: ${e.message}"
        // Return safe default - empty files, let image existence check decide
        return [files: [], method: "error", error: e.message]
    }
}

// Create and upload build manifest (Windows compatible)
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
    
    // Upload manifest to Artifactory (Windows curl)
    withCredentials([usernamePassword(
        credentialsId: 'artifactory-credentials',
        usernameVariable: 'ARTIFACTORY_USER',
        passwordVariable: 'ARTIFACTORY_PASS'
    )]) {
        bat """
            curl -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% ^
                 -T ${manifestFile} ^
                 "https://${env.DOCKER_REGISTRY}/artifactory/${env.DOCKER_REPO}/${manifestPath}/${appName}/${version}.json"
        """
    }
    
    echo "[MANIFEST] Uploaded ${manifestPath}/${appName}/${version}.json"
}

// ================================================================================
// ENHANCED CLEANUP FUNCTIONS
// ================================================================================

// Main cleanup function for docker-dev images (branch-aware + time-based)
def cleanupDevImages() {
    echo "[CLEANUP] Starting enhanced docker-dev cleanup..."
    echo "[CLEANUP] Strategy: Remove images from deleted/merged branches + images older than ${env.DEV_RETENTION_DAYS} days"
    
    withCredentials([usernamePassword(
        credentialsId: 'artifactory-credentials',
        usernameVariable: 'ARTIFACTORY_USER',
        passwordVariable: 'ARTIFACTORY_PASS'
    )]) {
        try {
            // Step 1: Get list of all active Git branches (improved method)
            echo "\n[CLEANUP] Step 1: Fetching active branches from Git..."

            // Use multiple methods to ensure we get accurate branch information
            bat "git remote prune origin 2>nul || exit 0"
            bat "git fetch --prune origin 2>nul || exit 0"

            def activeBranches = []

            // Method 1: Use git ls-remote to get definitive list of remote branches
            try {
                def remoteOutput = bat(
                    script: '@git ls-remote --heads origin 2>nul',
                    returnStdout: true
                ).trim()

                echo "[CLEANUP] Using git ls-remote for accurate branch detection"
                remoteOutput.split('\r?\n').each { line ->
                    if (line && line.contains('refs/heads/')) {
                        def branchName = line.split('refs/heads/')[1].trim()
                        if (branchName) {
                            // Clean the branch name to match image tag format
                            def cleanName = branchName
                                .replaceAll('[^a-zA-Z0-9._-]', '-')
                                .toLowerCase()
                            activeBranches.add(cleanName)
                        }
                    }
                }
            } catch (Exception e) {
                echo "[CLEANUP] git ls-remote failed: ${e.message}, falling back to git branch -r"

                // Fallback: Use git branch -r
                def branchOutput = bat(
                    script: '@git branch -r 2>nul',
                    returnStdout: true
                ).trim()

                branchOutput.split('\r?\n').each { branch ->
                    if (branch && branch.trim() && !branch.contains('HEAD')) {
                        // Clean the branch name to match image tag format
                        def cleanName = branch.trim()
                            .replace('origin/', '')
                            .replaceAll('[^a-zA-Z0-9._-]', '-')
                            .toLowerCase()
                        activeBranches.add(cleanName)
                    }
                }
            }

            echo "[CLEANUP] Found ${activeBranches.size()} active branches:"
            activeBranches.each { echo "  - ${it}" }
            
            // Step 2: Get list of all app folders in docker-dev from Artifactory
            echo "\n[CLEANUP] Step 2: Fetching docker-dev structure from Artifactory..."

            def appsUrl = "https://${env.DOCKER_REGISTRY}/artifactory/api/storage/${env.DOCKER_REPO}/${env.DOCKER_DEV_PATH}"
            echo "[CLEANUP] API URL: ${appsUrl}"

            def appsResponse = bat(
                script: """
                    @curl -s -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% "${appsUrl}" 2>nul
                """,
                returnStdout: true
            ).trim()
            
            // Parse apps from JSON response
            def apps = []
            try {
                echo "[CLEANUP] API Response length: ${appsResponse.length()}"
                echo "[CLEANUP] API Response preview: ${appsResponse.take(200)}..."

                if (appsResponse && appsResponse.trim() && appsResponse.contains('{')) {
                    def appParser = new groovy.json.JsonSlurper()
                    def appsJson = appParser.parseText(appsResponse)

                    if (appsJson.children) {
                        appsJson.children.each { child ->
                            if (child.folder && !child.uri.startsWith('/.')) {
                                apps.add(child.uri.substring(1))  // Remove leading '/'
                            }
                        }
                    }
                } else {
                    echo "[CLEANUP] Invalid or empty API response, trying fallback parsing"
                    // Fallback to simple parsing
                    if (appsResponse.contains('"uri"')) {
                        appsResponse.split('"uri"\\s*:\\s*"')[1..-1].each { part ->
                            def appName = part.split('"')[0].replaceAll('/', '')
                            if (appName && !appName.contains('.')) {
                                apps.add(appName)
                            }
                        }
                    }
                }
            } catch (Exception e) {
                echo "[CLEANUP] Error parsing apps JSON: ${e.message}"
                echo "[CLEANUP] Raw response: ${appsResponse}"
                // Fallback to simple parsing
                if (appsResponse.contains('"uri"')) {
                    appsResponse.split('"uri"\\s*:\\s*"')[1..-1].each { part ->
                        def appName = part.split('"')[0].replaceAll('/', '')
                        if (appName && !appName.contains('.')) {
                            apps.add(appName)
                        }
                    }
                }
            }
            
            echo "[CLEANUP] Found ${apps.size()} apps in docker-dev: ${apps.join(', ')}"
            
            def totalDeleted = 0
            def totalKept = 0
            def totalSizeFreed = 0
            
            // Get current date for time-based cleanup
            def cutoffDate = ''
            try {
                cutoffDate = bat(
                    script: """
                        @powershell -Command "(Get-Date).AddDays(-${env.DEV_RETENTION_DAYS}).ToString('yyyy-MM-ddTHH:mm:ss')"
                    """,
                    returnStdout: true
                ).trim()
                echo "[CLEANUP] Will also delete images created before: ${cutoffDate}"
            } catch (Exception e) {
                echo "[CLEANUP] Could not calculate cutoff date using PowerShell: ${e.message}"
                echo "[CLEANUP] Trying alternative date calculation..."
                try {
                    // Fallback: use current timestamp minus retention days in seconds
                    def currentTime = System.currentTimeMillis()
                    def retentionMillis = Integer.parseInt(env.DEV_RETENTION_DAYS) * 24 * 60 * 60 * 1000
                    def cutoffTime = new Date(currentTime - retentionMillis)
                    cutoffDate = cutoffTime.format('yyyy-MM-ddTHH:mm:ss')
                    echo "[CLEANUP] Using fallback cutoff date: ${cutoffDate}"
                } catch (Exception e2) {
                    echo "[CLEANUP] All date calculation methods failed: ${e2.message}"
                    cutoffDate = '' // Will skip time-based cleanup
                }
            }
            
            // Step 3: Process each app
            apps.each { app ->
                echo "\n[CLEANUP] Processing ${app}..."
                
                // Get all tags/images for this app
                def tagsUrl = "https://${env.DOCKER_REGISTRY}/artifactory/api/docker/${env.DOCKER_REPO}/v2/${env.DOCKER_DEV_PATH}/${app}/tags/list"
                def tagsResponse = bat(
                    script: """
                        @curl -s -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% "${tagsUrl}" 2>nul
                    """,
                    returnStdout: true
                ).trim()
                
                // Parse tags
                def tags = []
                try {
                    echo "  Tags API Response length: ${tagsResponse.length()}"
                    echo "  Tags API Response preview: ${tagsResponse.take(200)}..."

                    if (tagsResponse && tagsResponse.trim() && tagsResponse.contains('{')) {
                        def tagParser = new groovy.json.JsonSlurper()
                        def tagsJson = tagParser.parseText(tagsResponse)
                        if (tagsJson.tags) {
                            tags = tagsJson.tags
                        }
                    } else {
                        echo "  Invalid tags response, trying fallback parsing"
                        // Fallback parsing
                        if (tagsResponse.contains('"tags"')) {
                            def tagsSection = tagsResponse.split('"tags"\\s*:\\s*\\[')[1].split('\\]')[0]
                            tagsSection.split(',').each { tag ->
                                def cleanTag = tag.replaceAll('["\r\n\\s]', '')
                                if (cleanTag) {
                                    tags.add(cleanTag)
                                }
                            }
                        }
                    }
                } catch (Exception e) {
                    echo "  Error parsing tags JSON: ${e.message}"
                    echo "  Raw tags response: ${tagsResponse}"
                    // Fallback parsing
                    if (tagsResponse.contains('"tags"')) {
                        def tagsSection = tagsResponse.split('"tags"\\s*:\\s*\\[')[1].split('\\]')[0]
                        tagsSection.split(',').each { tag ->
                            def cleanTag = tag.replaceAll('["\r\n\\s]', '')
                            if (cleanTag) {
                                tags.add(cleanTag)
                            }
                        }
                    }
                }
                
                echo "  Found ${tags.size()} tags/images"
                
                def appDeleted = 0
                def appKept = 0
                
                // Step 4: Decide which tags to delete
                tags.each { tag ->
                    def shouldDelete = false
                    def reason = ""
                    
                    // Check 1: Branch existence (improved matching)
                    def branchFound = false
                    def tagLower = tag.toLowerCase()

                    echo "    Checking tag: ${tag}"

                    activeBranches.each { branch ->
                        def branchLower = branch.toLowerCase()
                        // Check multiple patterns:
                        // 1. tag starts with "branch-" (feature branch pattern)
                        // 2. tag equals branch name exactly
                        // 3. tag starts with branch name followed by dash and commit hash
                        if (tagLower.startsWith(branchLower + '-') ||
                            tagLower == branchLower ||
                            (tagLower.contains('-') && tagLower.split('-')[0] == branchLower)) {
                            branchFound = true
                            echo "      ✓ Branch found: ${branch}"
                        }
                    }

                    if (!branchFound) {
                        // Don't delete if it's from main/master branches
                        if (!tagLower.startsWith('main-') && !tagLower.startsWith('master-') &&
                            !tagLower.equals('main') && !tagLower.equals('master')) {
                            shouldDelete = true
                            reason = "branch no longer exists"
                            echo "      ✗ Branch not found - will delete"
                        } else {
                            echo "      ✓ Main/master branch - keeping"
                        }
                    }
                    
                    // Check 2: Age (if we have cutoff date and not already marked for deletion)
                    if (!shouldDelete && cutoffDate) {
                        // Get image metadata to check creation date
                        def metadataUrl = "https://${env.DOCKER_REGISTRY}/artifactory/api/storage/${env.DOCKER_REPO}/${env.DOCKER_DEV_PATH}/${app}/${tag}"
                        def metadataResponse = bat(
                            script: """
                                @curl -s -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% "${metadataUrl}" 2>nul
                            """,
                            returnStdout: true
                        ).trim()
                        
                        if (metadataResponse.contains('"created"')) {
                            def created = metadataResponse.split('"created"\\s*:\\s*"')[1].split('"')[0]
                            if (created < cutoffDate) {
                                shouldDelete = true
                                reason = "older than ${env.DEV_RETENTION_DAYS} days"
                            }
                        }
                    }
                    
                    // Execute deletion or keep
                    if (shouldDelete) {
                        if (params.DRY_RUN_CLEANUP) {
                            echo "    [DRY RUN] Would delete ${app}:${tag} - ${reason}"
                            appDeleted++
                        } else {
                            echo "    ✗ Deleting ${app}:${tag} - ${reason}"

                            def deletionSuccess = false
                            def dockerSuccess = false
                            def artifactorySuccess = false

                            // Method 1: Delete via Docker API (removes tag)
                            def dockerDeleteUrl = "https://${env.DOCKER_REGISTRY}/artifactory/api/docker/${env.DOCKER_REPO}/v2/${env.DOCKER_DEV_PATH}/${app}/tags/${tag}"
                            echo "      Attempting Docker API deletion: ${dockerDeleteUrl}"

                            def dockerResponse = bat(
                                script: """
                                    @curl -s -w "HTTPSTATUS:%%{http_code}" -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% ^
                                         -X DELETE "${dockerDeleteUrl}"
                                """,
                                returnStdout: true
                            ).trim()

                            def dockerHttpStatus = dockerResponse.contains('HTTPSTATUS:') ?
                                dockerResponse.split('HTTPSTATUS:')[1] : '000'

                            if (dockerHttpStatus == '200' || dockerHttpStatus == '204' || dockerHttpStatus == '404') {
                                dockerSuccess = true
                                echo "      Docker API deletion: SUCCESS (HTTP ${dockerHttpStatus})"
                            } else {
                                echo "      Docker API deletion: FAILED (HTTP ${dockerHttpStatus})"
                                echo "      Response: ${dockerResponse}"
                            }

                            // Method 2: Delete via Artifactory REST API (removes folder structure)
                            def artifactoryDeleteUrl = "https://${env.DOCKER_REGISTRY}/artifactory/${env.DOCKER_REPO}/${env.DOCKER_DEV_PATH}/${app}/${tag}"
                            echo "      Attempting Artifactory deletion: ${artifactoryDeleteUrl}"

                            def artifactoryResponse = bat(
                                script: """
                                    @curl -s -w "HTTPSTATUS:%%{http_code}" -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% ^
                                         -X DELETE "${artifactoryDeleteUrl}"
                                """,
                                returnStdout: true
                            ).trim()

                            def artifactoryHttpStatus = artifactoryResponse.contains('HTTPSTATUS:') ?
                                artifactoryResponse.split('HTTPSTATUS:')[1] : '000'

                            if (artifactoryHttpStatus == '200' || artifactoryHttpStatus == '204' || artifactoryHttpStatus == '404') {
                                artifactorySuccess = true
                                echo "      Artifactory deletion: SUCCESS (HTTP ${artifactoryHttpStatus})"
                            } else {
                                echo "      Artifactory deletion: FAILED (HTTP ${artifactoryHttpStatus})"
                                echo "      Response: ${artifactoryResponse}"
                            }

                            // Both methods should succeed for complete deletion
                            if (dockerSuccess && artifactorySuccess) {
                                echo "      ✓ COMPLETE DELETION SUCCESS: ${app}:${tag}"
                                appDeleted++
                                deletionSuccess = true
                            } else if (dockerSuccess || artifactorySuccess) {
                                echo "      ⚠ PARTIAL DELETION: ${app}:${tag} (Docker: ${dockerSuccess}, Artifactory: ${artifactorySuccess})"
                                appDeleted++ // Still count as deleted since at least one method worked
                                deletionSuccess = true
                            } else {
                                echo "      ✗ DELETION FAILED: ${app}:${tag} - both methods failed"
                            }
                        }
                    } else {
                        echo "    ✓ Keeping ${app}:${tag} - branch still active"
                        appKept++
                    }
                }
                
                // Check if app folder is now empty and delete it completely
                if (appDeleted > 0 && appKept == 0) {
                    if (params.DRY_RUN_CLEANUP) {
                        echo "  [DRY RUN] Would delete empty app folder and all its contents: ${env.DOCKER_DEV_PATH}/${app}"
                    } else {
                        echo "  Deleting empty app folder and all its contents: ${app}"

                        // Delete the entire app folder (this will remove all subfolders including sha256, _uploads, etc.)
                        def deleteFolderUrl = "https://${env.DOCKER_REGISTRY}/artifactory/${env.DOCKER_REPO}/${env.DOCKER_DEV_PATH}/${app}"
                        echo "    Attempting folder deletion: ${deleteFolderUrl}"

                        def folderResponse = bat(
                            script: """
                                @curl -s -w "HTTPSTATUS:%%{http_code}" -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% ^
                                     -X DELETE "${deleteFolderUrl}?recursive=1"
                            """,
                            returnStdout: true
                        ).trim()

                        def folderHttpStatus = folderResponse.contains('HTTPSTATUS:') ?
                            folderResponse.split('HTTPSTATUS:')[1] : '000'

                        if (folderHttpStatus == '200' || folderHttpStatus == '204') {
                            echo "    ✓ Successfully deleted app folder: ${app} (HTTP ${folderHttpStatus})"
                        } else if (folderHttpStatus == '404') {
                            echo "    ✓ App folder already deleted: ${app} (HTTP ${folderHttpStatus})"
                        } else {
                            echo "    ✗ Failed to delete app folder: ${app} (HTTP ${folderHttpStatus})"
                            echo "    Response: ${folderResponse}"

                            // Try to get more information about what's in the folder
                            echo "    Checking folder contents..."
                            def checkResponse = bat(
                                script: """
                                    @curl -s -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% ^
                                         "https://${env.DOCKER_REGISTRY}/artifactory/api/storage/${env.DOCKER_REPO}/${env.DOCKER_DEV_PATH}/${app}"
                                """,
                                returnStdout: true
                            ).trim()
                            echo "    Folder contents: ${checkResponse.take(200)}..."
                        }
                    }
                }
                
                totalDeleted += appDeleted
                totalKept += appKept
                
                echo "  Summary for ${app}: ${appDeleted} deleted, ${appKept} kept"
            }
            
            // Step 5: Run garbage collection to clean up orphaned blobs
            if (totalDeleted > 0 && !params.DRY_RUN_CLEANUP) {
                echo "\n[CLEANUP] Step 5: Running Docker registry garbage collection..."
                try {
                    // Trigger garbage collection to remove orphaned blobs
                    def gcResult = bat(
                        script: """
                            @curl -s -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% ^
                                 -X POST "https://${env.DOCKER_REGISTRY}/artifactory/api/system/storage/gc" ^
                                 -H "Content-Type: application/json" 2>nul
                        """,
                        returnStatus: true
                    )

                    if (gcResult == 0) {
                        echo "[CLEANUP] Garbage collection triggered successfully"
                    } else {
                        echo "[CLEANUP] Garbage collection trigger failed (this is optional)"
                    }
                } catch (Exception e) {
                    echo "[CLEANUP] Could not trigger garbage collection: ${e.message}"
                }
            }

            // Step 6: Overall summary
            echo "\n[CLEANUP] ========== DOCKER-DEV CLEANUP SUMMARY =========="
            echo "[CLEANUP] Images deleted: ${totalDeleted}"
            echo "[CLEANUP] Images kept: ${totalKept}"
            if (params.DRY_RUN_CLEANUP) {
                echo "[CLEANUP] This was a DRY RUN - no actual deletions performed"
            } else if (totalDeleted > 0) {
                echo "[CLEANUP] Garbage collection has been triggered to clean up orphaned storage"
            }
            echo "[CLEANUP] =================================================="
            
        } catch (Exception e) {
            echo "[CLEANUP] Error during docker-dev cleanup: ${e.message}"
            echo "[CLEANUP] Stack trace: ${e.printStackTrace()}"
        }
    }
}

// Cleanup specific branch
def cleanupSpecificBranch(branchName) {
    echo "[CLEANUP] Cleaning up specific branch: ${branchName}"
    
    def cleanBranchName = branchName
        .replaceAll('[^a-zA-Z0-9._-]', '-')
        .toLowerCase()
    
    withCredentials([usernamePassword(
        credentialsId: 'artifactory-credentials',
        usernameVariable: 'ARTIFACTORY_USER',
        passwordVariable: 'ARTIFACTORY_PASS'
    )]) {
        // Get list of apps
        def appsUrl = "https://${env.DOCKER_REGISTRY}/artifactory/api/storage/${env.DOCKER_REPO}/${env.DOCKER_DEV_PATH}"
        def appsResponse = bat(
            script: """
                @curl -s -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% "${appsUrl}" 2>nul
            """,
            returnStdout: true
        ).trim()
        
        def apps = []
        try {
            if (appsResponse && appsResponse.trim() && appsResponse.contains('{')) {
                def parser = new groovy.json.JsonSlurper()
                def appsJson = parser.parseText(appsResponse)
                if (appsJson.children) {
                    appsJson.children.each { child ->
                        if (child.folder) {
                            apps.add(child.uri.substring(1))
                        }
                    }
                }
            }
        } catch (Exception e) {
            echo "[CLEANUP] Error parsing apps for specific branch cleanup: ${e.message}"
            echo "[CLEANUP] Raw response: ${appsResponse}"
        }
        
        def totalDeleted = 0
        
        apps.each { app ->
            echo "\n[CLEANUP] Checking ${app} for branch ${cleanBranchName}..."
            
            // Get tags for this app
            def tagsUrl = "https://${env.DOCKER_REGISTRY}/artifactory/api/docker/${env.DOCKER_REPO}/v2/${env.DOCKER_DEV_PATH}/${app}/tags/list"
            def tagsResponse = bat(
                script: """
                    @curl -s -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% "${tagsUrl}" 2>nul
                """,
                returnStdout: true
            ).trim()
            
            def tags = []
            try {
                if (tagsResponse && tagsResponse.trim() && tagsResponse.contains('{')) {
                    def parser = new groovy.json.JsonSlurper()
                    def tagsJson = parser.parseText(tagsResponse)
                    tags = tagsJson.tags ?: []
                }
            } catch (Exception e) {
                echo "  Error parsing tags for branch cleanup: ${e.message}"
                echo "  Raw tags response: ${tagsResponse}"
            }
            
            // Delete matching tags
            tags.each { tag ->
                if (tag.toLowerCase().startsWith(cleanBranchName + '-')) {
                    if (params.DRY_RUN_CLEANUP) {
                        echo "  [DRY RUN] Would delete ${app}:${tag}"
                        totalDeleted++
                    } else {
                        echo "  Deleting ${app}:${tag}"

                        def dockerSuccess = false
                        def artifactorySuccess = false

                        // Delete via Docker API
                        def dockerDeleteUrl = "https://${env.DOCKER_REGISTRY}/artifactory/api/docker/${env.DOCKER_REPO}/v2/${env.DOCKER_DEV_PATH}/${app}/tags/${tag}"
                        def dockerResponse = bat(
                            script: """
                                @curl -s -w "HTTPSTATUS:%%{http_code}" -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% ^
                                     -X DELETE "${dockerDeleteUrl}"
                            """,
                            returnStdout: true
                        ).trim()

                        def dockerHttpStatus = dockerResponse.contains('HTTPSTATUS:') ?
                            dockerResponse.split('HTTPSTATUS:')[1] : '000'
                        dockerSuccess = (dockerHttpStatus == '200' || dockerHttpStatus == '204' || dockerHttpStatus == '404')

                        // Delete via Artifactory REST API
                        def artifactoryDeleteUrl = "https://${env.DOCKER_REGISTRY}/artifactory/${env.DOCKER_REPO}/${env.DOCKER_DEV_PATH}/${app}/${tag}"
                        def artifactoryResponse = bat(
                            script: """
                                @curl -s -w "HTTPSTATUS:%%{http_code}" -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% ^
                                     -X DELETE "${artifactoryDeleteUrl}"
                            """,
                            returnStdout: true
                        ).trim()

                        def artifactoryHttpStatus = artifactoryResponse.contains('HTTPSTATUS:') ?
                            artifactoryResponse.split('HTTPSTATUS:')[1] : '000'
                        artifactorySuccess = (artifactoryHttpStatus == '200' || artifactoryHttpStatus == '204' || artifactoryHttpStatus == '404')

                        if (dockerSuccess && artifactorySuccess) {
                            echo "    ✓ Successfully deleted ${app}:${tag}"
                            totalDeleted++
                        } else {
                            echo "    ⚠ Partial deletion ${app}:${tag} (Docker: ${dockerSuccess}, Artifactory: ${artifactorySuccess})"
                            if (dockerSuccess || artifactorySuccess) {
                                totalDeleted++ // Count partial success
                            }
                        }
                    }
                }
            }
        }
        
        echo "\n[CLEANUP] Deleted ${totalDeleted} images for branch: ${branchName}"
        
        // Also cleanup metadata for this branch
        cleanupBranchMetadata(cleanBranchName)
    }
}

// Cleanup metadata for a specific branch
def cleanupBranchMetadata(branchName) {
    echo "[CLEANUP] Cleaning metadata for branch: ${branchName}"
    
    withCredentials([usernamePassword(
        credentialsId: 'artifactory-credentials',
        usernameVariable: 'ARTIFACTORY_USER',
        passwordVariable: 'ARTIFACTORY_PASS'
    )]) {
        // Clean up temporary-builds metadata
        def metadataUrl = "https://${env.DOCKER_REGISTRY}/artifactory/api/storage/${env.DOCKER_REPO}/${env.TEMP_BUILDS_PATH}"
        def metadataResponse = bat(
            script: """
                @curl -s -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% "${metadataUrl}" 2>nul
            """,
            returnStdout: true
        ).trim()
        
        try {
            if (metadataResponse && metadataResponse.trim() && metadataResponse.contains('{')) {
                def parser = new groovy.json.JsonSlurper()
                def metadataJson = parser.parseText(metadataResponse)
                if (metadataJson.children) {
                    metadataJson.children.each { child ->
                        if (child.uri.contains(branchName)) {
                            if (params.DRY_RUN_CLEANUP) {
                                echo "  [DRY RUN] Would delete metadata: ${child.uri}"
                            } else {
                                echo "  Deleting metadata: ${child.uri}"
                                def deleteUrl = "https://${env.DOCKER_REGISTRY}/artifactory/${env.DOCKER_REPO}/${env.TEMP_BUILDS_PATH}${child.uri}"
                                bat """
                                    @curl -s -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% ^
                                         -X DELETE "${deleteUrl}" 2>nul
                                """
                            }
                        }
                    }
                }
            }
        } catch (Exception e) {
            echo "[CLEANUP] Error cleaning metadata: ${e.message}"
            echo "[CLEANUP] Raw metadata response: ${metadataResponse}"
        }
    }
}

// Enhanced cleanup for docker-latest images
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
    
    withCredentials([usernamePassword(
        credentialsId: 'artifactory-credentials',
        usernameVariable: 'ARTIFACTORY_USER',
        passwordVariable: 'ARTIFACTORY_PASS'
    )]) {
        // Get list of apps in docker-latest
        def appsUrl = "https://${env.DOCKER_REGISTRY}/artifactory/api/storage/${env.DOCKER_REPO}/${env.DOCKER_LATEST_PATH}"
        def appsResponse = bat(
            script: """
                @curl -s -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% "${appsUrl}" 2>nul
            """,
            returnStdout: true
        ).trim()
        
        def apps = []
        try {
            if (appsResponse && appsResponse.trim() && appsResponse.contains('{')) {
                def parser = new groovy.json.JsonSlurper()
                def appsJson = parser.parseText(appsResponse)
                if (appsJson.children) {
                    appsJson.children.each { child ->
                        if (child.folder) {
                            apps.add(child.uri.substring(1))
                        }
                    }
                }
            }
        } catch (Exception e) {
            echo "[CLEANUP] Error parsing apps for latest cleanup: ${e.message}"
            echo "[CLEANUP] Raw response: ${appsResponse}"
        }
        
        echo "[CLEANUP] Found ${apps.size()} apps in docker-latest"
        
        apps.each { app ->
            echo "\n[CLEANUP] Processing ${app}..."
            
            // Get all versions for this app
            def versionsUrl = "https://${env.DOCKER_REGISTRY}/artifactory/api/docker/${env.DOCKER_REPO}/v2/${env.DOCKER_LATEST_PATH}/${app}/tags/list"
            def versionsResponse = bat(
                script: """
                    @curl -s -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% "${versionsUrl}" 2>nul
                """,
                returnStdout: true
            ).trim()
            
            def versions = []
            try {
                if (versionsResponse && versionsResponse.trim() && versionsResponse.contains('{')) {
                    def parser = new groovy.json.JsonSlurper()
                    def versionsJson = parser.parseText(versionsResponse)
                    versions = versionsJson.tags ?: []
                }
            } catch (Exception e) {
                echo "  Error parsing versions for latest cleanup: ${e.message}"
                echo "  Raw versions response: ${versionsResponse}"
            }
            
            // Filter out 'latest' tag and sort versions
            def semanticVersions = versions.findAll { 
                it != 'latest' && it.matches('^\\d+\\.\\d+\\.\\d+$') 
            }
            
            // Sort versions (newest first)
            semanticVersions = semanticVersions.sort { a, b ->
                def aParts = a.split('\\.').collect { Integer.parseInt(it) }
                def bParts = b.split('\\.').collect { Integer.parseInt(it) }
                
                for (int i = 0; i < 3; i++) {
                    if (aParts[i] != bParts[i]) {
                        return bParts[i] - aParts[i]  // Descending order
                    }
                }
                return 0
            }
            
            echo "  Found ${semanticVersions.size()} versions"
            
            // Determine which versions to keep/delete
            def versionsToKeep = []
            def versionsToDelete = []
            
            semanticVersions.eachWithIndex { version, index ->
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
                if (params.DRY_RUN_CLEANUP) {
                    echo "    [DRY RUN] Would delete ${app}:${version}"
                } else {
                    def deleteUrl = "https://${env.DOCKER_REGISTRY}/artifactory/${env.DOCKER_REPO}/${env.DOCKER_LATEST_PATH}/${app}/${version}"
                    bat """
                        @curl -s -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% ^
                             -X DELETE "${deleteUrl}" 2>nul
                    """
                }
            }
            
            if (versionsToDelete.size() > 0) {
                echo "  Deleted ${versionsToDelete.size()} old versions"
            } else {
                echo "  No versions to delete"
            }
        }
    }
}

// Cleanup temporary build manifests
def cleanupTempManifests() {
    echo "[CLEANUP] Cleaning temporary build manifests older than ${env.DEV_RETENTION_DAYS} days..."
    
    withCredentials([usernamePassword(
        credentialsId: 'artifactory-credentials',
        usernameVariable: 'ARTIFACTORY_USER',
        passwordVariable: 'ARTIFACTORY_PASS'
    )]) {
        try {
            // Get cutoff date
            def cutoffDate = bat(
                script: """
                    @powershell -Command "(Get-Date).AddDays(-${env.DEV_RETENTION_DAYS}).ToString('yyyy-MM-ddTHH:mm:ss')"
                """,
                returnStdout: true
            ).trim()
            
            echo "[CLEANUP] Will delete manifests created before: ${cutoffDate}"
            
            // Get all manifests
            def manifestsUrl = "https://${env.DOCKER_REGISTRY}/artifactory/api/storage/${env.DOCKER_REPO}/${env.TEMP_BUILDS_PATH}"
            def manifestsResponse = bat(
                script: """
                    @curl -s -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% "${manifestsUrl}" 2>nul
                """,
                returnStdout: true
            ).trim()
            
            def deleted = 0

            try {
                if (manifestsResponse && manifestsResponse.trim() && manifestsResponse.contains('{')) {
                    def parser = new groovy.json.JsonSlurper()
                    def manifestsJson = parser.parseText(manifestsResponse)
                    if (manifestsJson.children) {
                        manifestsJson.children.each { child ->
                            if (!child.folder) {
                                // Get file metadata
                                def fileUrl = "https://${env.DOCKER_REGISTRY}/artifactory/api/storage/${env.DOCKER_REPO}/${env.TEMP_BUILDS_PATH}${child.uri}"
                                def fileResponse = bat(
                                    script: """
                                        @curl -s -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% "${fileUrl}" 2>nul
                                    """,
                                    returnStdout: true
                                ).trim()

                                if (fileResponse.contains('"created"')) {
                                    def created = fileResponse.split('"created"\\s*:\\s*"')[1].split('"')[0]
                                    if (created < cutoffDate) {
                                        if (params.DRY_RUN_CLEANUP) {
                                            echo "  [DRY RUN] Would delete manifest: ${child.uri}"
                                            deleted++
                                        } else {
                                            echo "  Deleting old manifest: ${child.uri}"
                                            def deleteUrl = "https://${env.DOCKER_REGISTRY}/artifactory/${env.DOCKER_REPO}/${env.TEMP_BUILDS_PATH}${child.uri}"
                                            bat """
                                                @curl -s -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% ^
                                                     -X DELETE "${deleteUrl}" 2>nul
                                            """
                                            deleted++
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                echo "[CLEANUP] Deleted ${deleted} old manifests"
            } catch (Exception e) {
                echo "[CLEANUP] Error cleaning manifests: ${e.message}"
                echo "[CLEANUP] Raw manifests response: ${manifestsResponse}"
            }
        } catch (Exception e) {
            echo "[CLEANUP] Error calculating cutoff date: ${e.message}"
        }
    }
}

// Force delete entire app folder (use with caution)
def forceDeleteApp(appName) {
    echo "[CLEANUP] Force deleting entire app folder: ${appName}"
    echo "[CLEANUP] WARNING: This will delete ALL versions and tags for ${appName}"

    withCredentials([usernamePassword(
        credentialsId: 'artifactory-credentials',
        usernameVariable: 'ARTIFACTORY_USER',
        passwordVariable: 'ARTIFACTORY_PASS'
    )]) {
        if (params.DRY_RUN_CLEANUP) {
            echo "[DRY RUN] Would force delete entire app folder: ${env.DOCKER_DEV_PATH}/${appName}"
            echo "[DRY RUN] This would remove all tags, sha256 folders, _uploads, and manifests"
        } else {
            // Delete the entire app folder recursively
            def deleteFolderUrl = "https://${env.DOCKER_REGISTRY}/artifactory/${env.DOCKER_REPO}/${env.DOCKER_DEV_PATH}/${appName}"

            echo "[CLEANUP] Deleting: ${deleteFolderUrl}"
            def deleteResult = bat(
                script: """
                    @curl -s -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% ^
                         -X DELETE "${deleteFolderUrl}?recursive=1" 2>nul
                """,
                returnStatus: true
            )

            if (deleteResult == 0) {
                echo "[CLEANUP] Successfully force deleted app folder: ${appName}"

                // Trigger garbage collection
                echo "[CLEANUP] Triggering garbage collection..."
                bat """
                    @curl -s -u %ARTIFACTORY_USER%:%ARTIFACTORY_PASS% ^
                         -X POST "https://${env.DOCKER_REGISTRY}/artifactory/api/system/storage/gc" ^
                         -H "Content-Type: application/json" 2>nul || echo "GC trigger completed"
                """
            } else {
                echo "[CLEANUP] Failed to force delete app folder: ${appName}"
            }
        }
    }
}