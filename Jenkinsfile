pipeline {
    agent any

    triggers {
        // Poll SCM every 2 minutes for changes
        //pollSCM('H/2 * * * *')
        // Alternative: Use webhook trigger (recommended)
        githubPush()
    }

    environment {
        // Define any environment variables if needed
        PYTHON_VERSION = '3.9'
    }

    stages {
        stage('Checkout') {
            steps {
                echo "[CHECKOUT] Checking out repository..."
                checkout scm

                // Get commit information
                script {
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
                }

                echo "[COMMIT] ${env.GIT_COMMIT_HASH}"
                echo "[AUTHOR] ${env.GIT_AUTHOR}"
                echo "[MESSAGE] ${env.GIT_COMMIT_MSG}"
            }
        }
        
        stage('Detect Python Files') {
            steps {
                script {
                    echo "[DETECTION] Scanning for Python files in commit and repository..."

                    // Get list of changed files in the current commit
                    def output = bat(
                        script: '@git diff-tree --no-commit-id --name-only -r HEAD',
                        returnStdout: true
                    ).trim()
                    def changedFiles = output.split('\n')

                    // Filter for Python files in commit
                    def pythonFiles = changedFiles.findAll { file ->
                        file.endsWith('.py')
                    }

                    if (pythonFiles.size() > 0) {
                        echo "[SUCCESS] Found ${pythonFiles.size()} Python file(s) in this commit:"
                        pythonFiles.each { file ->
                            echo "[FILE] ${file}"
                        }

                        // Store python files for next stages
                        env.PYTHON_FILES_FOUND = pythonFiles.join(',')
                        env.HAS_PYTHON_FILES = 'true'

                        // Get file details
                        pythonFiles.each { file ->
                            if (fileExists(file)) {
                                def fileSize = powershell(
                                    script: "(Get-Content '${file}' | Measure-Object -Line).Lines",
                                    returnStdout: true
                                ).trim()
                                echo "[STATS] ${file}: ${fileSize} lines"
                            }
                        }
                    } else {
                        echo "[INFO] No Python files found in this commit"
                        env.HAS_PYTHON_FILES = 'false'
                    }

                    // Scan ALL Python files in repository recursively
                    echo "[SCAN] All Python files in repository (recursive scan):"
                    def allPythonFiles = powershell(
                        script: 'Get-ChildItem -Path . -Filter "*.py" -Recurse | Sort-Object FullName | ForEach-Object { $_.FullName.Replace((Get-Location).Path, ".").Replace("\\", "/") }',
                        returnStdout: true
                    ).trim()

                    if (allPythonFiles) {
                        def fileCount = 0
                        allPythonFiles.split('\n').each { file ->
                            if (file.trim()) {
                                fileCount++
                                echo "[REPOSITORY] ${file.trim()}"
                            }
                        }
                        echo "[TOTAL] Found ${fileCount} Python files in entire repository"
                    } else {
                        echo "[INFO] No Python files found in repository"
                    }
                }
            }
        }
        
        stage('Process Python Files') {
            when {
                environment name: 'HAS_PYTHON_FILES', value: 'true'
            }
            steps {
                script {
                    echo "[PROCESSING] Analyzing detected Python files..."

                    def pythonFiles = env.PYTHON_FILES_FOUND.split(',')

                    pythonFiles.each { file ->
                        if (fileExists(file)) {
                            echo "[ANALYZE] Processing file: ${file}"

                            // Check Python syntax
                            def syntaxCheck = ""
                            def syntaxOK = true

                            try {
                                syntaxCheck = bat(
                                    script: "@python -m py_compile \"${file}\" 2>&1 || echo SYNTAX_ERROR",
                                    returnStdout: true
                                ).trim()

                                if (syntaxCheck.contains('SYNTAX_ERROR') || syntaxCheck.contains('SyntaxError')) {
                                    syntaxOK = false
                                }
                            } catch (Exception e) {
                                syntaxCheck = "Error checking syntax: ${e.message}"
                                syntaxOK = false
                            }

                            if (!syntaxOK) {
                                echo "[ERROR] Syntax error detected in ${file}"
                                echo "[DETAILS] ${syntaxCheck}"
                            } else {
                                echo "[SUCCESS] Syntax validation passed for ${file}"
                            }

                            // Count functions and classes
                            def functionCount = "0"
                            def classCount = "0"

                            try {
                                functionCount = powershell(
                                    script: "(Select-String -Path '${file}' -Pattern '^def ' | Measure-Object).Count",
                                    returnStdout: true
                                ).trim()

                                classCount = powershell(
                                    script: "(Select-String -Path '${file}' -Pattern '^class ' | Measure-Object).Count",
                                    returnStdout: true
                                ).trim()
                            } catch (Exception e) {
                                echo "[WARNING] Could not count functions/classes: ${e.message}"
                            }

                            echo "[METRICS] Functions: ${functionCount}, Classes: ${classCount}"

                            // Show first few lines
                            echo "[PREVIEW] First 5 lines of ${file}:"
                            try {
                                powershell "Get-Content '${file}' -Head 5 | ForEach-Object { '      ' + \$_ }"
                            } catch (Exception e) {
                                echo "[WARNING] Could not display file content: ${e.message}"
                            }
                        }
                    }
                }
            }
        }
        
        stage('Summary') {
            steps {
                script {
                    echo "[SUMMARY] BUILD SUMMARY"
                    echo "=================="
                    echo "[REPOSITORY] ${env.GIT_URL ?: 'Local repository'}"
                    echo "[BRANCH] ${env.GIT_BRANCH ?: 'Unknown'}"
                    echo "[COMMIT] ${env.GIT_COMMIT_HASH}"
                    echo "[AUTHOR] ${env.GIT_AUTHOR}"
                    echo "[MESSAGE] ${env.GIT_COMMIT_MSG}"

                    if (env.HAS_PYTHON_FILES == 'true') {
                        echo "[PYTHON_DETECTED] YES"
                        echo "[PYTHON_FILES] ${env.PYTHON_FILES_FOUND}"
                        echo "[STATUS] Python file processing completed successfully!"
                    } else {
                        echo "[PYTHON_DETECTED] NO"
                        echo "[INFO] This commit doesn't contain Python files"
                    }

                    echo "[COMPLETED] Build finished at: ${new Date()}"
                }
            }
        }
    }

    post {
        always {
            echo "[CLEANUP] Cleaning up workspace..."
            // Add any cleanup steps here
        }
        success {
            echo "[SUCCESS] Pipeline completed successfully!"
        }
        failure {
            echo "[FAILURE] Pipeline failed!"
        }
        changed {
            echo "[CHANGED] Pipeline status changed from previous run"
        }
    }
}
