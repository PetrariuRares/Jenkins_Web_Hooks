pipeline {
    agent any

    triggers {
        // Poll SCM every 2 minutes for changes
        pollSCM('H/2 * * * *')
        // Alternative: Use webhook trigger (recommended)
        // githubPush()
    }

    environment {
        // Define any environment variables if needed
        PYTHON_VERSION = '3.9'
    }

    stages {
        stage('Checkout') {
            steps {
                echo "🔄 Checking out repository..."
                checkout scm

                // Get commit information - Windows compatible
                script {
                    if (isUnix()) {
                        // Unix/Linux commands
                        env.GIT_COMMIT_MSG = sh(
                            script: 'git log -1 --pretty=%B',
                            returnStdout: true
                        ).trim()

                        env.GIT_AUTHOR = sh(
                            script: 'git log -1 --pretty=%an',
                            returnStdout: true
                        ).trim()

                        env.GIT_COMMIT_HASH = sh(
                            script: 'git rev-parse HEAD',
                            returnStdout: true
                        ).trim()
                    } else {
                        // Windows commands
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
                }

                echo "📝 Commit: ${env.GIT_COMMIT_HASH}"
                echo "👤 Author: ${env.GIT_AUTHOR}"
                echo "💬 Message: ${env.GIT_COMMIT_MSG}"
            }
        }
        
        stage('Detect Python Files') {
            steps {
                script {
                    echo "🐍 Detecting Python files in the commit..."

                    // Get list of changed files in the current commit - Windows compatible
                    def changedFiles = []
                    if (isUnix()) {
                        changedFiles = sh(
                            script: 'git diff-tree --no-commit-id --name-only -r HEAD',
                            returnStdout: true
                        ).trim().split('\n')
                    } else {
                        def output = bat(
                            script: '@git diff-tree --no-commit-id --name-only -r HEAD',
                            returnStdout: true
                        ).trim()
                        changedFiles = output.split('\n')
                    }

                    // Filter for Python files
                    def pythonFiles = changedFiles.findAll { file ->
                        file.endsWith('.py')
                    }

                    if (pythonFiles.size() > 0) {
                        echo "✅ Found ${pythonFiles.size()} Python file(s) in this commit:"
                        pythonFiles.each { file ->
                            echo "   📄 ${file}"
                        }

                        // Store python files for next stages
                        env.PYTHON_FILES_FOUND = pythonFiles.join(',')
                        env.HAS_PYTHON_FILES = 'true'

                        // Get file details - Windows compatible
                        pythonFiles.each { file ->
                            if (fileExists(file)) {
                                def fileSize = "0"
                                if (isUnix()) {
                                    fileSize = sh(
                                        script: "wc -l < '${file}' || echo '0'",
                                        returnStdout: true
                                    ).trim()
                                } else {
                                    fileSize = powershell(
                                        script: "(Get-Content '${file}' | Measure-Object -Line).Lines",
                                        returnStdout: true
                                    ).trim()
                                }
                                echo "   📊 ${file}: ${fileSize} lines"
                            }
                        }
                    } else {
                        echo "ℹ️  No Python files found in this commit"
                        env.HAS_PYTHON_FILES = 'false'
                    }

                    // Also check for all Python files in the repository - Windows compatible
                    echo "\n🔍 All Python files in repository:"
                    def allPythonFiles = ""
                    if (isUnix()) {
                        allPythonFiles = sh(
                            script: 'find . -name "*.py" -type f | head -20',
                            returnStdout: true
                        ).trim()
                    } else {
                        allPythonFiles = powershell(
                            script: 'Get-ChildItem -Path . -Filter "*.py" -Recurse | Select-Object -First 20 | ForEach-Object { $_.FullName.Replace((Get-Location).Path + "\\", ".\\") }',
                            returnStdout: true
                        ).trim()
                    }

                    if (allPythonFiles) {
                        allPythonFiles.split('\n').each { file ->
                            if (file.trim()) {
                                echo "   📄 ${file.trim()}"
                            }
                        }
                    } else {
                        echo "   ℹ️  No Python files found in repository"
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
                    echo "⚙️  Processing detected Python files..."

                    def pythonFiles = env.PYTHON_FILES_FOUND.split(',')

                    pythonFiles.each { file ->
                        if (fileExists(file)) {
                            echo "\n🔍 Analyzing: ${file}"

                            // Check Python syntax - Windows compatible
                            def syntaxCheck = ""
                            def syntaxOK = true

                            try {
                                if (isUnix()) {
                                    syntaxCheck = sh(
                                        script: "python -m py_compile '${file}' 2>&1 || echo 'SYNTAX_ERROR'",
                                        returnStdout: true
                                    ).trim()
                                } else {
                                    syntaxCheck = bat(
                                        script: "@python -m py_compile \"${file}\" 2>&1 || echo SYNTAX_ERROR",
                                        returnStdout: true
                                    ).trim()
                                }

                                if (syntaxCheck.contains('SYNTAX_ERROR') || syntaxCheck.contains('SyntaxError')) {
                                    syntaxOK = false
                                }
                            } catch (Exception e) {
                                syntaxCheck = "Error checking syntax: ${e.message}"
                                syntaxOK = false
                            }

                            if (!syntaxOK) {
                                echo "   ❌ Syntax error detected in ${file}"
                                echo "   ${syntaxCheck}"
                            } else {
                                echo "   ✅ Syntax OK for ${file}"
                            }

                            // Count functions and classes - Windows compatible
                            def functionCount = "0"
                            def classCount = "0"

                            try {
                                if (isUnix()) {
                                    functionCount = sh(
                                        script: "grep -c '^def ' '${file}' || echo '0'",
                                        returnStdout: true
                                    ).trim()

                                    classCount = sh(
                                        script: "grep -c '^class ' '${file}' || echo '0'",
                                        returnStdout: true
                                    ).trim()
                                } else {
                                    functionCount = powershell(
                                        script: "(Select-String -Path '${file}' -Pattern '^def ' | Measure-Object).Count",
                                        returnStdout: true
                                    ).trim()

                                    classCount = powershell(
                                        script: "(Select-String -Path '${file}' -Pattern '^class ' | Measure-Object).Count",
                                        returnStdout: true
                                    ).trim()
                                }
                            } catch (Exception e) {
                                echo "   ⚠️  Could not count functions/classes: ${e.message}"
                            }

                            echo "   📊 Functions: ${functionCount}, Classes: ${classCount}"

                            // Show first few lines - Windows compatible
                            echo "   📖 First 5 lines:"
                            try {
                                if (isUnix()) {
                                    sh "head -5 '${file}' | sed 's/^/      /'"
                                } else {
                                    powershell "Get-Content '${file}' -Head 5 | ForEach-Object { '      ' + \$_ }"
                                }
                            } catch (Exception e) {
                                echo "   ⚠️  Could not display file content: ${e.message}"
                            }
                        }
                    }
                }
            }
        }
        
        stage('Summary') {
            steps {
                script {
                    echo "\n📋 BUILD SUMMARY"
                    echo "=================="
                    echo "🔗 Repository: ${env.GIT_URL ?: 'Local repository'}"
                    echo "🏷️  Branch: ${env.GIT_BRANCH ?: 'Unknown'}"
                    echo "📝 Commit: ${env.GIT_COMMIT_HASH}"
                    echo "👤 Author: ${env.GIT_AUTHOR}"
                    echo "💬 Message: ${env.GIT_COMMIT_MSG}"
                    
                    if (env.HAS_PYTHON_FILES == 'true') {
                        echo "🐍 Python files detected: YES"
                        echo "📄 Files: ${env.PYTHON_FILES_FOUND}"
                        echo "✅ Python file processing completed successfully!"
                    } else {
                        echo "🐍 Python files detected: NO"
                        echo "ℹ️  This commit doesn't contain Python files"
                    }
                    
                    echo "🎉 Build completed at: ${new Date()}"
                }
            }
        }
    }
    
    post {
        always {
            echo "🧹 Cleaning up workspace..."
            // Add any cleanup steps here
        }
        success {
            echo "✅ Pipeline completed successfully!"
        }
        failure {
            echo "❌ Pipeline failed!"
        }
        changed {
            echo "🔄 Pipeline status changed from previous run"
        }
    }
}
