# SWE-Bench Project Knowledge

## Core Mission
This project evaluates AI coding assistants on real-world GitHub issues using the SWE-Bench framework.

## Aider vs Codebuff Comparison

### Aider
- Full-featured coding assistant that integrates with git repositories
- Uses LLMs (like GPT-4) for code generation and editing
- Has built-in git integration for version control
- Maintains chat history and context across interactions
- Can handle multiple files and complex refactoring tasks
- Uses a repo map to understand project structure
- Supports auto-testing of changes via test_cmd
- Handles file edits through structured edit blocks
- Manages temperature and reflection settings for LLM interaction
- Tracks costs of API usage

### Codebuff
- More focused tool specifically for code editing
- Uses PTY-based interaction model
- Simpler architecture - single command per interaction
- No built-in git integration
- Stateless - doesn't maintain chat history
- Works on individual files rather than whole repos
- Uses simpler instruction format
- No built-in test integration
- No cost tracking needed (not using paid APIs)
- Faster execution since no API calls

### Codebuff Interface
- Simple CLI with two optional arguments:
  1. project-directory: Where to look for code (defaults to current dir)
  2. initial-prompt: First instruction to execute
- Runs interactively in terminal
- No configuration files needed
- No special markup or commands required in prompts
- Uses standard input/output for communication

### Key Architectural Differences
1. **Interaction Model**
   - Aider: Chat-based with persistent context
   - Codebuff: Command-line with PTY interface

2. **State Management** 
   - Aider: Maintains git repo state and chat history
   - Codebuff: Stateless, processes one command at a time

3. **File Handling**
   - Aider: Can edit multiple files with search/replace
   - Codebuff: Focused on single file edits

4. **Testing Integration**
   - Aider: Built-in test command support
   - Codebuff: No native test integration

## Migration Strategy
When adapting harness.py for Codebuff:
1. Remove LLM-specific code (temperature, costs, etc)
2. Simplify file handling to single-file focus
3. Replace git operations with direct file ops
4. Adapt the PTY-based interaction model
5. Remove chat history management
6. Simplify the test integration

### Key Migration Tasks
1. Modify execute_codebuff() to match codebuff's CLI interface
2. Remove chat history and git integration code
3. Adapt test running to work without git
4. Simplify the file handling to work with codebuff's model
5. Remove LLM-specific configuration

## Style Guide
- Keep code modular and focused
- Maintain clear error handling
- Document key functions
- Use type hints where helpful
- Follow existing project structure

## Technical Goals
- [ ] Adapt harness.py for Codebuff
- [ ] Maintain compatibility with SWE-Bench framework
- [ ] Preserve test evaluation capabilities
- [ ] Keep docker integration working

## Links
- [SWE-Bench Framework](https://github.com/princeton-nlp/SWE-bench)
