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
                
                // Get commit information
                script {
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
                    
                    // Get list of changed files in the current commit
                    def changedFiles = sh(
                        script: 'git diff-tree --no-commit-id --name-only -r HEAD',
                        returnStdout: true
                    ).trim().split('\n')
                    
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
                        
                        // Get file details
                        pythonFiles.each { file ->
                            if (fileExists(file)) {
                                def fileSize = sh(
                                    script: "wc -l < '${file}' || echo '0'",
                                    returnStdout: true
                                ).trim()
                                echo "   📊 ${file}: ${fileSize} lines"
                            }
                        }
                    } else {
                        echo "ℹ️  No Python files found in this commit"
                        env.HAS_PYTHON_FILES = 'false'
                    }
                    
                    // Also check for all Python files in the repository
                    echo "\n🔍 All Python files in repository:"
                    def allPythonFiles = sh(
                        script: 'find . -name "*.py" -type f | head -20',
                        returnStdout: true
                    ).trim()
                    
                    if (allPythonFiles) {
                        allPythonFiles.split('\n').each { file ->
                            echo "   📄 ${file}"
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
                            
                            // Check Python syntax
                            def syntaxCheck = sh(
                                script: "python -m py_compile '${file}' 2>&1 || echo 'SYNTAX_ERROR'",
                                returnStdout: true
                            ).trim()
                            
                            if (syntaxCheck.contains('SYNTAX_ERROR')) {
                                echo "   ❌ Syntax error detected in ${file}"
                                echo "   ${syntaxCheck}"
                            } else {
                                echo "   ✅ Syntax OK for ${file}"
                            }
                            
                            // Count functions and classes
                            def functionCount = sh(
                                script: "grep -c '^def ' '${file}' || echo '0'",
                                returnStdout: true
                            ).trim()
                            
                            def classCount = sh(
                                script: "grep -c '^class ' '${file}' || echo '0'",
                                returnStdout: true
                            ).trim()
                            
                            echo "   📊 Functions: ${functionCount}, Classes: ${classCount}"
                            
                            // Show first few lines
                            echo "   📖 First 5 lines:"
                            sh "head -5 '${file}' | sed 's/^/      /'"
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
