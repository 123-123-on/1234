# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Microsoft To Do style task management application built with Flask, SQLite, and Tailwind CSS. It's a complete task management system that was converted from a Windows Settings interface clone to a full-featured todo application.

## Development Commands

### Running the Application
```bash
# Quick start (recommended)
python app.py

# Alternative: Initialize database first, then run
python database.py
python app.py

# Database operations
python database.py          # Initialize/reset database with default data
python check_db.py          # Check database integrity and view data
```

### Installation
```bash
pip install -r requirements.txt
```

The application runs on `http://127.0.0.1:5000` in development mode with debug enabled.

## Architecture Overview

### Backend Structure (Flask)
- **app.py**: Main Flask application with all API endpoints
- **database.py**: Database schema definition and initialization
- **check_db.py**: Database integrity checking utility

### Frontend Structure
- **templates/index.html**: Single-page application with Microsoft To Do design
- **static/js/main.js**: Complete frontend logic with ES6+ features
- Uses Tailwind CSS via CDN for styling with Windows 11 design language

### Database Schema
SQLite database (`settings.db`) with three main tables:
- **tasks**: Task records with title, description, priority, due_date, etc.
- **task_lists**: Task categories (我的一天, 重要, 已计划, etc.)
- **user_preferences**: User settings including theme and display preferences

## Key Features & Implementation

### Task Management System
- Full CRUD operations for tasks and task lists
- Priority levels (high/medium/low) with visual indicators
- Due date management with overdue highlighting
- Important task marking with star icons
- Task completion tracking with timestamps

### User Interface
- Microsoft To Do inspired design with Windows 11 Fluent Design
- Responsive layout with sidebar navigation
- Three circular action buttons with hover animations
- Dark/light theme switching with CSS custom properties
- Smooth animations and micro-interactions

### AI Assistant Integration
- AI chat panel with draggable interface
- Local fallback responses when API is unavailable
- Configurable AI provider (OpenAI-compatible APIs)
- Task context awareness for intelligent responses

### API Endpoints Structure
```
/api/task_lists     - GET/POST for task list management
/api/tasks          - GET/POST for task CRUD
/api/tasks/{id}     - GET/PUT/DELETE for individual tasks
/api/search         - GET for task search
/api/stats          - GET for task statistics
/api/user_preferences - GET/PUT for user settings
/api/ai/chat        - POST for AI assistant
/api/ai/config      - GET/PUT for AI configuration
```

## Development Guidelines

### Database Operations
- Always use `get_db_connection()` for database access
- Use parameterized queries to prevent SQL injection
- Database changes should update both `database.py` and provide migration logic

### Frontend Development
- All JavaScript is in `main.js` with proper error handling
- Uses async/await for API calls with loading states
- Implements debounced search to reduce API calls
- Theme switching requires updating CSS custom properties

### Styling Conventions
- Uses Tailwind CSS with Windows 11 design tokens
- CSS custom properties for theme variables
- Responsive design with mobile-first approach
- Animations use cubic-bezier easing functions

### AI Integration
- Supports OpenAI-compatible APIs with configurable base URLs
- Graceful degradation to local rule-based responses
- Context awareness using current task data
- Typing indicators and message history management

## Configuration Files

### AI Configuration (ai_config.json)
Contains AI assistant settings including model, API keys, system prompts, and UI preferences. API keys are masked in GET responses for security.

### Default Data Distribution
The application initializes with 7 task lists and sample tasks distributed across them to demonstrate functionality.

## Development Patterns

### Error Handling
- Frontend shows user-friendly notifications
- Backend returns appropriate HTTP status codes
- API responses include error messages for debugging

### Performance Considerations
- Implements local statistics updates to reduce API calls
- Uses debouncing for search input
- Lazy loading for task list navigation
- Efficient DOM updates with minimal reflows

### Security Notes
- API endpoints handle basic validation
- SQL injection prevention with parameterized queries
- API key masking in configuration responses
- CORS enabled for development

## Testing & Debugging

### Database Debugging
```bash
python check_db.py  # View current database state
```

### Common Issues
- Port 5000 conflicts: Change port in app.py
- Database corruption: Delete settings.db and run database.py
- Theme issues: Check CSS custom properties in index.html

This codebase is well-structured for a Flask application with clear separation between backend logic, frontend presentation, and data management.