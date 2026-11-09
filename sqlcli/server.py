"""Local Web Dashboard & Studio server for SQLCLI (MySQL, SQLite, NoSQL)."""

from __future__ import annotations

import http.server
import json
import socketserver
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Any

from .autopilot import generate_autopilot_plan
from .diagnostics import analyze_error
from .knowledge import TOPICS
from .multi_engine import MultiEngineManager
from .queries import get_query, load_queries, save_query


def get_dashboard_html() -> str:
    """Return self-contained, beginner-friendly SQLite Studio Web Dashboard HTML."""
    return """<!DOCTYPE html>
<html lang="en" data-theme="obsidian">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SQLCLI Studio — Database Workbench & Visual Studio</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root, [data-theme="obsidian"] {
      --bg-canvas: #090B10;
      --bg-surface-1: #0F131C;
      --bg-surface-2: #161B26;
      --bg-surface-3: #1E2535;
      --bg-glass: rgba(15, 19, 28, 0.92);
      --border-subtle: rgba(255, 255, 255, 0.08);
      --border-interactive: rgba(255, 255, 255, 0.16);
      --border-focus: #38BDF8;
      --text-primary: #F8FAFC;
      --text-secondary: #94A3B8;
      --text-muted: #64748B;
      --accent-primary: #38BDF8;
      --accent-secondary: #818CF8;
      --status-success: #10B981;
      --status-warning: #F59E0B;
      --status-danger: #F43F5E;
      --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }
    [data-theme="daylight"] {
      --bg-canvas: #F8FAFC;
      --bg-surface-1: #FFFFFF;
      --bg-surface-2: #F1F5F9;
      --bg-surface-3: #E2E8F0;
      --bg-glass: rgba(255, 255, 255, 0.95);
      --border-subtle: rgba(0, 0, 0, 0.08);
      --border-interactive: rgba(0, 0, 0, 0.16);
      --border-focus: #0284C7;
      --text-primary: #0F172A;
      --text-secondary: #475569;
      --text-muted: #94A3B8;
      --accent-primary: #0284C7;
      --accent-secondary: #6366F1;
      --status-success: #059669;
      --status-warning: #D97706;
      --status-danger: #E11D48;
      --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg-canvas);
      color: var(--text-primary);
      font-family: var(--font-sans);
      height: 100vh;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }
    .tabular-nums { font-variant-numeric: tabular-nums; }
    
    /* Top Header */
    header {
      background: var(--bg-glass);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border-subtle);
      height: 54px;
      padding: 0 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      z-index: 10;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 700;
      font-size: 15px;
      letter-spacing: -0.02em;
    }
    .brand-icon {
      width: 28px;
      height: 28px;
      background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #000;
      font-weight: 900;
      font-size: 14px;
    }
    .brand-badge {
      background: rgba(56, 189, 248, 0.15);
      color: var(--accent-primary);
      font-size: 11px;
      font-weight: 700;
      padding: 2px 8px;
      border-radius: 4px;
      border: 1px solid rgba(56, 189, 248, 0.3);
    }
    .engine-switcher {
      display: flex;
      background: var(--bg-surface-2);
      padding: 3px;
      border-radius: 8px;
      border: 1px solid var(--border-subtle);
    }
    .engine-btn {
      background: transparent;
      border: none;
      color: var(--text-secondary);
      font-size: 12px;
      font-weight: 600;
      padding: 6px 14px;
      border-radius: 6px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
    }
    .engine-btn.active {
      background: var(--bg-surface-1);
      color: var(--text-primary);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    }
    .header-actions {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .btn {
      background: var(--bg-surface-2);
      border: 1px solid var(--border-subtle);
      color: var(--text-primary);
      font-size: 12px;
      font-weight: 500;
      padding: 6px 12px;
      border-radius: 6px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
    }
    .btn:hover { background: var(--bg-surface-3); border-color: var(--border-interactive); }
    .btn-primary {
      background: var(--accent-primary);
      color: #000;
      border: none;
      font-weight: 600;
    }
    .btn-primary:hover { opacity: 0.9; }
    .btn-success {
      background: var(--status-success);
      color: #FFF;
      border: none;
      font-weight: 600;
    }
    .btn-success:hover { opacity: 0.9; }

    /* Layout */
    .app-body {
      display: grid;
      grid-template-columns: 310px 1fr 310px;
      flex: 1;
      overflow: hidden;
    }

    /* Left Sidebar */
    .sidebar {
      background: var(--bg-surface-1);
      border-right: 1px solid var(--border-subtle);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .sidebar-tabs {
      display: flex;
      border-bottom: 1px solid var(--border-subtle);
      background: var(--bg-surface-2);
    }
    .tab-btn {
      flex: 1;
      padding: 10px 0;
      font-size: 11px;
      font-weight: 600;
      text-align: center;
      background: transparent;
      border: none;
      color: var(--text-muted);
      cursor: pointer;
      border-bottom: 2px solid transparent;
      transition: all 0.15s ease;
    }
    .tab-btn.active {
      color: var(--accent-primary);
      border-bottom-color: var(--accent-primary);
      background: var(--bg-surface-1);
    }
    .tab-content {
      flex: 1;
      overflow-y: auto;
      padding: 12px;
    }
    .history-card {
      background: var(--bg-surface-2);
      border: 1px solid var(--border-subtle);
      border-radius: 6px;
      padding: 10px;
      margin-bottom: 8px;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .history-card:hover {
      border-color: var(--accent-primary);
      background: var(--bg-surface-3);
    }
    .history-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
    }
    .status-badge {
      font-size: 10px;
      font-weight: 700;
      padding: 2px 6px;
      border-radius: 4px;
      text-transform: uppercase;
    }
    .status-success { background: rgba(16, 185, 129, 0.15); color: var(--status-success); }
    .status-error { background: rgba(244, 63, 94, 0.15); color: var(--status-danger); }
    .history-code {
      font-family: var(--font-mono);
      font-size: 11px;
      color: var(--text-secondary);
      white-space: pre-wrap;
      word-break: break-all;
      max-height: 48px;
      overflow: hidden;
    }
    .schema-card {
      background: var(--bg-surface-2);
      border: 1px solid var(--border-subtle);
      border-radius: 6px;
      padding: 10px;
      margin-bottom: 8px;
    }
    .schema-title-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      cursor: pointer;
    }
    .schema-table-name {
      font-weight: 600;
      font-size: 13px;
      color: var(--text-primary);
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .schema-actions {
      display: flex;
      gap: 4px;
    }
    .schema-action-btn {
      background: var(--bg-surface-3);
      border: none;
      color: var(--text-secondary);
      padding: 3px 6px;
      border-radius: 4px;
      font-size: 10px;
      cursor: pointer;
    }
    .schema-action-btn:hover { color: var(--text-primary); background: var(--border-interactive); }
    .schema-cols {
      margin-top: 8px;
      padding-top: 8px;
      border-top: 1px solid var(--border-subtle);
      font-size: 11px;
      color: var(--text-muted);
      font-family: var(--font-mono);
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    /* Center Main Workspace */
    .workspace {
      display: flex;
      flex-direction: column;
      overflow: hidden;
      background: var(--bg-canvas);
    }

    /* Friendly Quick Action Bar */
    .quick-bar {
      padding: 8px 16px;
      background: var(--bg-surface-1);
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      align-items: center;
      gap: 8px;
      overflow-x: auto;
    }
    .quick-chip {
      background: var(--bg-surface-2);
      border: 1px solid var(--border-subtle);
      color: var(--text-secondary);
      font-size: 11px;
      padding: 4px 10px;
      border-radius: 14px;
      cursor: pointer;
      white-space: nowrap;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      transition: all 0.15s ease;
    }
    .quick-chip:hover {
      background: var(--bg-surface-3);
      border-color: var(--accent-primary);
      color: var(--text-primary);
    }
    .quick-chip-primary {
      background: rgba(56, 189, 248, 0.12);
      color: var(--accent-primary);
      border-color: rgba(56, 189, 248, 0.3);
      font-weight: 600;
    }
    .quick-chip-primary:hover {
      background: rgba(56, 189, 248, 0.2);
    }

    /* Autopilot Bar */
    .autopilot-bar {
      padding: 10px 16px;
      background: var(--bg-surface-1);
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      gap: 10px;
      align-items: center;
    }
    .autopilot-input {
      flex: 1;
      background: var(--bg-surface-2);
      border: 1px solid var(--border-subtle);
      border-radius: 6px;
      padding: 8px 14px;
      color: var(--text-primary);
      font-size: 13px;
      outline: none;
      transition: border-color 0.15s ease;
    }
    .autopilot-input:focus { border-color: var(--accent-primary); }

    /* Code Editor Section */
    .editor-section {
      height: 200px;
      background: var(--bg-surface-1);
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      flex-direction: column;
      position: relative;
    }
    .editor-toolbar {
      padding: 6px 16px;
      background: var(--bg-surface-2);
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 12px;
      color: var(--text-secondary);
    }
    .editor-textarea {
      flex: 1;
      background: transparent;
      border: none;
      color: var(--text-primary);
      font-family: var(--font-mono);
      font-size: 13px;
      padding: 12px 16px;
      resize: none;
      outline: none;
      line-height: 1.6;
    }

    /* Friendly Error HUD */
    .diagnostics-panel {
      display: none;
      background: rgba(244, 63, 94, 0.08);
      border: 1px solid var(--status-danger);
      margin: 12px 16px;
      padding: 14px 16px;
      border-radius: 8px;
      animation: fadeIn 0.2s ease;
    }
    .diagnostics-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 8px;
    }
    .diagnostics-title {
      font-weight: 700;
      font-size: 13px;
      color: var(--status-danger);
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .diagnostics-body {
      font-size: 12px;
      color: var(--text-primary);
      margin-bottom: 10px;
      line-height: 1.5;
    }
    .diagnostics-fix {
      font-size: 12px;
      color: var(--status-success);
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: rgba(16, 185, 129, 0.08);
      padding: 8px 12px;
      border-radius: 6px;
      border: 1px solid rgba(16, 185, 129, 0.25);
    }

    /* Results Grid */
    .results-section {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      background: var(--bg-surface-1);
    }
    .results-toolbar {
      padding: 8px 16px;
      background: var(--bg-surface-2);
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 12px;
    }
    .table-container {
      flex: 1;
      overflow: auto;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }
    th {
      background: var(--bg-surface-2);
      position: sticky;
      top: 0;
      padding: 8px 12px;
      text-align: left;
      font-weight: 600;
      color: var(--text-secondary);
      border-bottom: 1px solid var(--border-subtle);
      border-right: 1px solid var(--border-subtle);
      white-space: nowrap;
    }
    td {
      padding: 8px 12px;
      border-bottom: 1px solid var(--border-subtle);
      border-right: 1px solid var(--border-subtle);
      color: var(--text-primary);
      white-space: nowrap;
      font-family: var(--font-mono);
      font-size: 12px;
    }
    tr:hover td { background: var(--bg-surface-2); }
    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100%;
      color: var(--text-muted);
      gap: 12px;
      padding: 20px;
      text-align: center;
    }

    /* Right Tutor Drawer */
    .drawer {
      background: var(--bg-surface-1);
      border-left: 1px solid var(--border-subtle);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .drawer-header {
      padding: 12px 16px;
      border-bottom: 1px solid var(--border-subtle);
      font-weight: 600;
      font-size: 13px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .search-input {
      background: var(--bg-surface-2);
      border: 1px solid var(--border-subtle);
      border-radius: 6px;
      padding: 6px 10px;
      color: var(--text-primary);
      font-size: 12px;
      outline: none;
    }
    .search-input:focus { border-color: var(--accent-primary); }
    .topic-item {
      padding: 10px 14px;
      border-bottom: 1px solid var(--border-subtle);
      cursor: pointer;
      transition: background 0.15s ease;
    }
    .topic-item:hover { background: var(--bg-surface-2); }
    .topic-title { font-size: 12px; font-weight: 600; color: var(--text-primary); margin-bottom: 2px; }
    .topic-meta { font-size: 10px; color: var(--text-muted); }

    /* Modals */
    .modal-overlay {
      display: none;
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0, 0, 0, 0.7);
      backdrop-filter: blur(4px);
      z-index: 100;
      align-items: center;
      justify-content: center;
    }
    .modal-card {
      background: var(--bg-surface-1);
      border: 1px solid var(--border-interactive);
      border-radius: 10px;
      width: 520px;
      max-width: 90vw;
      max-height: 85vh;
      overflow-y: auto;
      padding: 20px;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
    }
    .modal-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }
    .modal-title { font-size: 16px; font-weight: 700; color: var(--text-primary); }
    .form-group { margin-bottom: 14px; }
    .form-label { display: block; font-size: 12px; font-weight: 600; margin-bottom: 6px; color: var(--text-secondary); }
    .form-input, .form-select {
      width: 100%;
      background: var(--bg-surface-2);
      border: 1px solid var(--border-subtle);
      border-radius: 6px;
      padding: 8px 12px;
      color: var(--text-primary);
      font-size: 13px;
      outline: none;
    }
    .col-row { display: grid; grid-template-columns: 2fr 1.5fr 1fr 30px; gap: 8px; margin-bottom: 8px; align-items: center; }

    @keyframes fadeIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
  </style>
</head>
<body>

  <!-- Top Header -->
  <header>
    <div class="brand">
      <div class="brand-icon">⚡</div>
      <span>SQLCLI Studio</span>
      <span class="brand-badge">Visual Database</span>
    </div>

    <!-- Multi-Engine Selector -->
    <div class="engine-switcher">
      <button class="engine-btn active" id="btn-sqlite" onclick="switchEngine('sqlite')">
        <span>📁</span> SQLite (Zero Setup)
      </button>
      <button class="engine-btn" id="btn-mysql" onclick="switchEngine('mysql')">
        <span>⚡</span> SQL (MySQL / XAMPP)
      </button>
      <button class="engine-btn" id="btn-nosql" onclick="switchEngine('nosql')">
        <span>📦</span> NoSQL (JSON Docs)
      </button>
    </div>

    <!-- Action Bar -->
    <div class="header-actions">
      <button class="btn btn-primary" onclick="openNewTableModal()">✨ New Table</button>
      <button class="btn" onclick="openInsertRowModal()">➕ Insert Row</button>
      <button class="btn btn-success" onclick="loadSampleData()">📥 Load Sample Data</button>
      <button class="btn" onclick="toggleTheme()">🌓 Theme</button>
    </div>
  </header>

  <!-- App Body Layout -->
  <div class="app-body">

    <!-- Left Sidebar: Tables, Previous Work, Saved -->
    <div class="sidebar">
      <div class="sidebar-tabs">
        <button class="tab-btn active" onclick="switchSidebarTab('schema')">TABLES & DATA</button>
        <button class="tab-btn" onclick="switchSidebarTab('history')">PREVIOUS WORK</button>
        <button class="tab-btn" onclick="switchSidebarTab('saved')">SAVED</button>
      </div>

      <!-- Schema Explorer Tab -->
      <div id="tab-schema" class="tab-content">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
          <span style="font-size: 11px; font-weight: 700; color: var(--text-muted);">CURRENT TABLES</span>
          <button class="btn" style="padding: 2px 8px; font-size: 11px;" onclick="fetchSchema()">Refresh</button>
        </div>
        <div id="schema-list"></div>
      </div>

      <!-- History / Previous Work Tab -->
      <div id="tab-history" class="tab-content" style="display: none;">
        <div id="history-list">
          <div style="text-align: center; color: var(--text-muted); padding: 20px;">No query history yet.</div>
        </div>
      </div>

      <!-- Saved Queries Tab -->
      <div id="tab-saved" class="tab-content" style="display: none;">
        <div id="saved-list"></div>
      </div>
    </div>

    <!-- Center Main Workspace -->
    <div class="workspace">

      <!-- Friendly Quick Action Chips (No SQL memorization needed) -->
      <div class="quick-bar">
        <span style="font-size: 11px; font-weight: 700; color: var(--text-muted); margin-right: 4px;">QUICK STARTERS:</span>
        <button class="quick-chip quick-chip-primary" onclick="runQuickQuery('all')">📋 View All Students</button>
        <button class="quick-chip" onclick="runQuickQuery('honor')">🔍 High GPA (&gt; 3.8)</button>
        <button class="quick-chip" onclick="runQuickQuery('sort')">📊 Top Ranked</button>
        <button class="quick-chip" onclick="runQuickQuery('group')">📈 Students by Major</button>
        <button class="quick-chip" onclick="runQuickQuery('join')">🔗 Join Courses</button>
      </div>

      <!-- Autopilot Bar -->
      <div class="autopilot-bar">
        <input type="text" id="autopilot-input" class="autopilot-input" placeholder="Autopilot: describe what you want in plain English (e.g. 'show students with GPA over 3.5' or 'create library books table')...">
        <button class="btn btn-primary" onclick="runAutopilot()">✈ Run Autopilot</button>
      </div>

      <!-- Code Editor Section -->
      <div class="editor-section">
        <div class="editor-toolbar">
          <span id="editor-dialect" style="font-weight: 600;">📁 SQLite Active</span>
          <div style="display: flex; gap: 8px;">
            <button class="btn" style="padding: 4px 10px;" onclick="clearEditor()">Clear</button>
            <button class="btn" style="padding: 4px 10px;" onclick="saveCurrentQuery()">Save</button>
            <button class="btn btn-primary" style="padding: 4px 16px; font-size: 13px;" onclick="runQuery()">▶ Run Query (Ctrl+Enter)</button>
          </div>
        </div>
        <textarea id="query-editor" class="editor-textarea" spellcheck="false" placeholder="Type SQL query or click any table or Quick Starter above..."></textarea>
      </div>

      <!-- Friendly Error HUD (Appears on Error) -->
      <div id="diagnostics-panel" class="diagnostics-panel">
        <div class="diagnostics-header">
          <div class="diagnostics-title">
            <span>⚠️</span>
            <span id="diag-friendly-title">Query Needs Attention</span>
          </div>
          <span id="diag-code" style="font-family: var(--font-mono); font-size: 11px; color: var(--text-muted);"></span>
        </div>
        <div id="diag-message" class="diagnostics-body"></div>
        <div id="diag-fix-box" class="diagnostics-fix">
          <span id="diag-fix-text"></span>
          <button class="btn btn-success" style="padding: 4px 12px; font-size: 11px;" onclick="applyAutoFix()">✨ Auto-Fix &amp; Run</button>
        </div>
      </div>

      <!-- Results Grid -->
      <div class="results-section">
        <div class="results-toolbar">
          <div style="display: flex; gap: 12px; align-items: center;">
            <span id="result-status" style="font-weight: 600; color: var(--text-primary);">Ready</span>
            <span id="result-meta" class="tabular-nums" style="color: var(--text-muted); font-size: 11px;"></span>
          </div>
          <div style="display: flex; gap: 8px;">
            <button class="btn" style="padding: 3px 8px; font-size: 11px;" onclick="exportResults('csv')">Export CSV</button>
            <button class="btn" style="padding: 3px 8px; font-size: 11px;" onclick="exportResults('json')">Export JSON</button>
          </div>
        </div>
        <div class="table-container" id="table-container">
          <div class="empty-state">
            <svg width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M4 7v10c0 2 1.5 3 3.5 3h9c2 0 3.5-1 3.5-3V7M4 7c0-2 1.5-3 3.5-3h9c2 0 3.5 1 3.5 3M4 7h16M9 11h6M9 15h4"/></svg>
            <div style="font-weight: 600; font-size: 14px;">No query results yet</div>
            <div style="font-size: 12px; max-width: 320px;">Click <b>"Load Sample Data"</b> at the top or pick any <b>Quick Starter</b> chip to see working data!</div>
          </div>
        </div>
      </div>

    </div>

    <!-- Right Drawer: W3Schools Tutor -->
    <div class="drawer">
      <div class="drawer-header">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>📚 SQL Tutor (W3Schools)</span>
          <span style="font-size: 10px; color: var(--text-muted);">60+ Topics</span>
        </div>
        <input type="text" id="tutor-search" class="search-input" placeholder="Search topics (e.g. join, select)..." oninput="filterTopics()">
      </div>
      <div id="topics-list" style="overflow-y: auto; flex: 1;"></div>
    </div>

  </div>

  <!-- Modal: Visual New Table Wizard -->
  <div id="new-table-modal" class="modal-overlay">
    <div class="modal-card">
      <div class="modal-header">
        <div class="modal-title">✨ Create New Table (Visual)</div>
        <button class="btn" onclick="closeModals()">✕</button>
      </div>
      <div class="form-group">
        <label class="form-label">Table Name</label>
        <input type="text" id="new-tbl-name" class="form-input" placeholder="e.g. students, products, orders">
      </div>
      <div class="form-group">
        <label class="form-label">Columns</label>
        <div id="col-rows-container">
          <div class="col-row">
            <input type="text" class="form-input col-name" value="id" placeholder="Column name">
            <select class="form-select col-type">
              <option value="INTEGER" selected>INTEGER</option>
              <option value="TEXT">TEXT</option>
              <option value="REAL">REAL (Decimal)</option>
              <option value="DATE">DATE</option>
            </select>
            <label style="font-size: 11px; display: flex; align-items: center; gap: 4px;">
              <input type="checkbox" class="col-pk" checked> PK
            </label>
            <span></span>
          </div>
          <div class="col-row">
            <input type="text" class="form-input col-name" value="name" placeholder="Column name">
            <select class="form-select col-type">
              <option value="TEXT" selected>TEXT</option>
              <option value="INTEGER">INTEGER</option>
              <option value="REAL">REAL (Decimal)</option>
              <option value="DATE">DATE</option>
            </select>
            <label style="font-size: 11px; display: flex; align-items: center; gap: 4px;">
              <input type="checkbox" class="col-pk"> PK
            </label>
            <button class="btn" style="padding: 2px 6px;" onclick="this.parentElement.remove()">✕</button>
          </div>
        </div>
        <button class="btn" style="margin-top: 8px;" onclick="addColumnRow()">+ Add Column</button>
      </div>
      <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px;">
        <button class="btn" onclick="closeModals()">Cancel</button>
        <button class="btn btn-primary" onclick="submitNewTable()">Create Table</button>
      </div>
    </div>
  </div>

  <!-- Modal: Visual Insert Row Wizard -->
  <div id="insert-row-modal" class="modal-overlay">
    <div class="modal-card">
      <div class="modal-header">
        <div class="modal-title">➕ Insert Row (Visual Form)</div>
        <button class="btn" onclick="closeModals()">✕</button>
      </div>
      <div class="form-group">
        <label class="form-label">Select Table</label>
        <select id="insert-tbl-select" class="form-select" onchange="renderInsertFormFields()"></select>
      </div>
      <div id="insert-fields-container" class="form-group"></div>
      <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px;">
        <button class="btn" onclick="closeModals()">Cancel</button>
        <button class="btn btn-primary" onclick="submitInsertRow()">Insert Record</button>
      </div>
    </div>
  </div>

  <script>
    let currentEngine = 'sqlite';
    let currentDiagnostics = null;
    let lastResults = { headers: [], rows: [] };
    let currentSchema = {};
    let allTopics = {};

    window.addEventListener('DOMContentLoaded', () => {
      switchEngine('sqlite');
      fetchTopics();
      fetchHistory();
      fetchSaved();

      // Ctrl+Enter run shortcut
      document.getElementById('query-editor').addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
          e.preventDefault();
          runQuery();
        }
      });
      // Enter on Autopilot input runs it
      document.getElementById('autopilot-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          runAutopilot();
        }
      });
    });

    function switchEngine(engine) {
      currentEngine = engine;
      document.querySelectorAll('.engine-btn').forEach(btn => btn.classList.remove('active'));
      const activeBtn = document.getElementById('btn-' + engine);
      if (activeBtn) activeBtn.classList.add('active');

      const dialectLabel = document.getElementById('editor-dialect');
      if (engine === 'sqlite') dialectLabel.textContent = '📁 SQLite (Zero-Setup workspace.sqlite)';
      else if (engine === 'mysql') dialectLabel.textContent = '⚡ MySQL (XAMPP localhost:3306)';
      else dialectLabel.textContent = '📦 NoSQL Document Store (workspace_nosql.db)';

      fetchSchema();
    }

    function switchSidebarTab(tab) {
      document.querySelectorAll('.sidebar-tabs .tab-btn').forEach(btn => btn.classList.remove('active'));
      document.querySelectorAll('.sidebar .tab-content').forEach(c => c.style.display = 'none');
      if (event && event.target) event.target.classList.add('active');
      const target = document.getElementById('tab-' + tab);
      if (target) target.style.display = 'block';
    }

    async function loadSampleData() {
      try {
        const res = await fetch('/api/demo', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ engine: currentEngine })
        });
        const data = await res.json();
        alert(data.message || 'Sample data loaded!');
        await fetchSchema();
        runQuickQuery('all');
      } catch (err) {
        alert('Failed to load sample data: ' + err);
      }
    }

    function runQuickQuery(type) {
      const editor = document.getElementById('query-editor');
      if (currentEngine === 'nosql') {
        if (type === 'all') editor.value = 'db.students.find({});';
        else if (type === 'honor') editor.value = 'db.students.find({"major": "Computer Science"});';
        else editor.value = 'show collections;';
        runQuery();
        return;
      }

      if (type === 'all') editor.value = 'SELECT * FROM students LIMIT 20;';
      else if (type === 'honor') editor.value = 'SELECT id, name, major, gpa FROM students WHERE gpa > 3.8 ORDER BY gpa DESC;';
      else if (type === 'sort') editor.value = 'SELECT id, name, gpa, major FROM students ORDER BY gpa DESC;';
      else if (type === 'group') editor.value = 'SELECT major, COUNT(*) AS student_count, ROUND(AVG(gpa), 2) AS avg_gpa FROM students GROUP BY major;';
      else if (type === 'join') editor.value = 'SELECT s.name, s.major, c.code, c.title FROM students s CROSS JOIN courses c LIMIT 10;';
      runQuery();
    }

    async function fetchSchema() {
      try {
        const res = await fetch(`/api/schema?engine=${currentEngine}`);
        const schema = await res.json();
        currentSchema = schema;
        const container = document.getElementById('schema-list');
        const tables = Object.keys(schema);

        if (tables.length === 0) {
          container.innerHTML = `
            <div style="text-align: center; padding: 24px 10px; color: var(--text-muted);">
              <div style="font-size: 13px; font-weight: 600; margin-bottom: 6px;">No tables yet</div>
              <p style="font-size: 11px; margin-bottom: 12px;">Click below to populate a demo database:</p>
              <button class="btn btn-primary" style="width: 100%; justify-content: center;" onclick="loadSampleData()">📥 Load Sample Students</button>
            </div>
          `;
          return;
        }

        container.innerHTML = tables.map(tbl => `
          <div class="schema-card">
            <div class="schema-title-row">
              <div class="schema-table-name" onclick="selectTable('${tbl}')">
                <span>📄</span> <b>${tbl}</b>
              </div>
              <div class="schema-actions">
                <button class="schema-action-btn" title="View Data" onclick="selectTable('${tbl}')">View</button>
                <button class="schema-action-btn" title="Insert Row" onclick="openInsertRowForTable('${tbl}')">+ Row</button>
                <button class="schema-action-btn" title="Drop Table" onclick="dropTablePrompt('${tbl}')">✕</button>
              </div>
            </div>
            <div class="schema-cols">
              ${(schema[tbl] || []).map(col => `<div>• ${col}</div>`).join('')}
            </div>
          </div>
        `).join('');
      } catch (err) {
        document.getElementById('schema-list').innerHTML = `<div style="color: var(--status-danger); padding: 10px;">Schema unavailable.</div>`;
      }
    }

    function selectTable(tbl) {
      const editor = document.getElementById('query-editor');
      if (currentEngine === 'nosql') {
        editor.value = `db.${tbl}.find({});`;
      } else {
        editor.value = `SELECT * FROM \\`${tbl}\\` LIMIT 50;`;
      }
      runQuery();
    }

    function dropTablePrompt(tbl) {
      if (confirm(`Are you sure you want to drop table '${tbl}'?`)) {
        const editor = document.getElementById('query-editor');
        editor.value = `DROP TABLE \\`${tbl}\\`;`;
        runQuery();
      }
    }

    async function runQuery() {
      const editor = document.getElementById('query-editor');
      const query = editor.value.trim();
      if (!query) return;

      const diagPanel = document.getElementById('diagnostics-panel');
      diagPanel.style.display = 'none';
      document.getElementById('result-status').textContent = 'Executing...';

      try {
        const res = await fetch('/api/execute', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query, engine: currentEngine })
        });
        const data = await res.json();

        if (data.error) {
          showFriendlyError(data);
          document.getElementById('result-status').textContent = 'Execution Error';
          document.getElementById('result-meta').textContent = `${data.elapsed_ms || 0}ms`;
        } else {
          lastResults = { headers: data.headers || [], rows: data.rows || [] };
          renderResultsTable(data.headers, data.rows);
          document.getElementById('result-status').textContent = `Success · ${data.count} row(s) affected`;
          document.getElementById('result-meta').textContent = `${(data.elapsed_ms || 0).toFixed(2)}ms`;
          fetchHistory();
          fetchSchema();
        }
      } catch (err) {
        showFriendlyError({ error: String(err) });
      }
    }

    function showFriendlyError(data) {
      const diagPanel = document.getElementById('diagnostics-panel');
      const diag = data.diagnostics || {};
      currentDiagnostics = diag;

      diagPanel.style.display = 'block';
      document.getElementById('diag-friendly-title').textContent = diag.error_type ? `Friendly Diagnosis: ${diag.error_type}` : 'Query Needs Attention';
      document.getElementById('diag-code').textContent = diag.error_code ? `Err #${diag.error_code}` : '';
      
      const humanMsg = diag.explanation || data.error;
      document.getElementById('diag-message').textContent = humanMsg;

      const fixBox = document.getElementById('diag-fix-box');
      if (diag.suggested_fix) {
        fixBox.style.display = 'flex';
        document.getElementById('diag-fix-text').textContent = diag.suggested_fix;
      } else {
        fixBox.style.display = 'none';
      }
    }

    function applyAutoFix() {
      if (!currentDiagnostics) return;
      const editor = document.getElementById('query-editor');
      let sql = editor.value;

      if (currentDiagnostics.corrected_sql) {
        editor.value = currentDiagnostics.corrected_sql;
        runQuery();
        return;
      }

      // Typo replacement
      if (currentDiagnostics.faulty_snippet && currentDiagnostics.suggested_fix) {
        const match = currentDiagnostics.suggested_fix.match(/replace '([^']+)' with '([^']+)'/i);
        if (match) {
          sql = sql.replace(new RegExp(match[1], 'i'), match[2]);
          editor.value = sql;
          runQuery();
          return;
        }
      }

      // If missing table recommendation
      if (currentDiagnostics.suggested_fix.includes("Change table name")) {
        const match = currentDiagnostics.suggested_fix.match(/to '([^']+)'/);
        if (match && currentDiagnostics.faulty_snippet) {
          sql = sql.replace(new RegExp(currentDiagnostics.faulty_snippet, 'g'), match[1]);
          editor.value = sql;
          runQuery();
          return;
        }
      }

      alert("Please review the suggested fix above and adjust the query in the editor.");
    }

    function renderResultsTable(headers, rows) {
      const container = document.getElementById('table-container');
      if (!headers || headers.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <span style="font-size: 24px;">✓</span>
            <div style="font-weight: 600; font-size: 14px;">Statement executed successfully</div>
            <div style="font-size: 12px; color: var(--text-muted);">No records were returned to display.</div>
          </div>
        `;
        return;
      }

      let html = `<table><thead><tr><th style="width: 40px; text-align: center;">#</th>`;
      html += headers.map(h => `<th>${escapeHtml(h)}</th>`).join('');
      html += `</tr></thead><tbody>`;

      if (!rows || rows.length === 0) {
        html += `<tr><td colspan="${headers.length + 1}" style="text-align: center; padding: 20px; color: var(--text-muted);">0 rows returned</td></tr>`;
      } else {
        rows.forEach((row, i) => {
          html += `<tr><td style="text-align: center; color: var(--text-muted); font-size: 11px;">${i + 1}</td>`;
          row.forEach(cell => {
            html += `<td>${escapeHtml(cell !== null ? String(cell) : 'NULL')}</td>`;
          });
          html += `</tr>`;
        });
      }
      html += `</tbody></table>`;
      container.innerHTML = html;
    }

    async function runAutopilot() {
      const goal = document.getElementById('autopilot-input').value.trim();
      if (!goal) return;

      try {
        const res = await fetch('/api/autopilot', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ goal, engine: currentEngine })
        });
        const data = await res.json();
        if (data.sql) {
          document.getElementById('query-editor').value = data.sql;
          runQuery();
        }
      } catch (err) {
        alert('Autopilot error: ' + err);
      }
    }

    async function fetchHistory() {
      try {
        const res = await fetch('/api/history');
        const history = await res.json();
        const container = document.getElementById('history-list');
        if (!history || history.length === 0) {
          container.innerHTML = '<div style="color: var(--text-muted); font-size: 12px; padding: 10px; text-align: center;">No history yet.</div>';
          return;
        }

        container.innerHTML = history.slice().reverse().map(item => `
          <div class="history-card" onclick="document.getElementById('query-editor').value = '${escapeHtml(item.query).replace(/'/g, "\\\\'")}'; runQuery();">
            <div class="history-header">
              <span class="status-badge ${item.status === 'SUCCESS' ? 'status-success' : 'status-error'}">${item.status}</span>
              <span class="tabular-nums" style="font-size: 10px; color: var(--text-muted);">${item.elapsed_ms || 0}ms · ${item.row_count || 0} rows</span>
            </div>
            <div class="history-code">${escapeHtml(item.query)}</div>
          </div>
        `).join('');
      } catch (err) {}
    }

    async function fetchTopics() {
      try {
        const res = await fetch('/api/topics');
        allTopics = await res.json();
        renderTopicsList(allTopics);
      } catch (err) {}
    }

    function renderTopicsList(topics) {
      const container = document.getElementById('topics-list');
      const keys = Object.keys(topics);
      if (keys.length === 0) {
        container.innerHTML = '<div style="padding: 12px; color: var(--text-muted); font-size: 12px;">No matching topics.</div>';
        return;
      }
      container.innerHTML = keys.map(k => `
        <div class="topic-item" onclick="loadTopicExample('${escapeHtml(topics[k].example).replace(/'/g, "\\\\'")}')">
          <div class="topic-title">${topics[k].name}</div>
          <div class="topic-meta">${topics[k].category}</div>
        </div>
      `).join('');
    }

    function filterTopics() {
      const q = document.getElementById('tutor-search').value.toLowerCase();
      const filtered = {};
      Object.keys(allTopics).forEach(k => {
        if (allTopics[k].name.toLowerCase().includes(q) || allTopics[k].category.toLowerCase().includes(q)) {
          filtered[k] = allTopics[k];
        }
      });
      renderTopicsList(filtered);
    }

    function loadTopicExample(example) {
      document.getElementById('query-editor').value = example;
      document.getElementById('query-editor').focus();
      runQuery();
    }

    async function fetchSaved() {
      try {
        const res = await fetch('/api/saved');
        const saved = await res.json();
        const container = document.getElementById('saved-list');
        const names = Object.keys(saved);
        if (names.length === 0) {
          container.innerHTML = '<div style="color: var(--text-muted); font-size: 12px; padding: 10px;">No saved queries yet.</div>';
          return;
        }
        container.innerHTML = names.map(n => `
          <div class="history-card" onclick="document.getElementById('query-editor').value = '${escapeHtml(saved[n]).replace(/'/g, "\\\\'")}';">
            <div style="font-weight: 600; font-size: 12px; margin-bottom: 4px;">${n}</div>
            <div class="history-code">${escapeHtml(saved[n])}</div>
          </div>
        `).join('');
      } catch (err) {}
    }

    async function saveCurrentQuery() {
      const sql = document.getElementById('query-editor').value.trim();
      if (!sql) return;
      const name = prompt('Enter a name for this saved query:');
      if (!name) return;
      await fetch('/api/saved', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, sql })
      });
      fetchSaved();
    }

    function clearEditor() {
      document.getElementById('query-editor').value = '';
      document.getElementById('query-editor').focus();
    }

    function exportResults(format) {
      if (!lastResults.headers || lastResults.headers.length === 0) return alert('No results to export.');
      let content = '', filename = `export_${Date.now()}.${format}`, mime = 'text/plain';
      if (format === 'csv') {
        content = lastResults.headers.join(',') + '\\n' +
          lastResults.rows.map(r => r.map(c => `"${String(c || '').replace(/"/g, '""')}"`).join(',')).join('\\n');
        mime = 'text/csv';
      } else {
        const objs = lastResults.rows.map(r => Object.fromEntries(lastResults.headers.map((h, i) => [h, r[i]])));
        content = JSON.stringify(objs, null, 2);
        mime = 'application/json';
      }
      const blob = new Blob([content], { type: mime });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      a.click();
    }

    /* Modals & Wizards */
    function openNewTableModal() {
      document.getElementById('new-table-modal').style.display = 'flex';
    }

    function closeModals() {
      document.querySelectorAll('.modal-overlay').forEach(m => m.style.display = 'none');
    }

    function addColumnRow() {
      const container = document.getElementById('col-rows-container');
      const div = document.createElement('div');
      div.className = 'col-row';
      div.innerHTML = `
        <input type="text" class="form-input col-name" placeholder="Column name">
        <select class="form-select col-type">
          <option value="TEXT">TEXT</option>
          <option value="INTEGER">INTEGER</option>
          <option value="REAL">REAL (Decimal)</option>
          <option value="DATE">DATE</option>
        </select>
        <label style="font-size: 11px; display: flex; align-items: center; gap: 4px;">
          <input type="checkbox" class="col-pk"> PK
        </label>
        <button class="btn" style="padding: 2px 6px;" onclick="this.parentElement.remove()">✕</button>
      `;
      container.appendChild(div);
    }

    async function submitNewTable() {
      const tableName = document.getElementById('new-tbl-name').value.trim();
      if (!tableName) return alert('Please enter a table name.');

      const rows = document.querySelectorAll('#col-rows-container .col-row');
      const columns = [];
      rows.forEach(r => {
        const name = r.querySelector('.col-name').value.trim();
        const type = r.querySelector('.col-type').value;
        const pk = r.querySelector('.col-pk').checked;
        if (name) columns.push({ name, type, pk });
      });

      if (columns.length === 0) return alert('Add at least one column.');

      try {
        const res = await fetch('/api/create_table', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ engine: currentEngine, table_name: tableName, columns })
        });
        const data = await res.json();
        if (data.error) alert('Error: ' + data.error);
        else {
          closeModals();
          fetchSchema();
          selectTable(tableName);
        }
      } catch (err) {
        alert('Failed: ' + err);
      }
    }

    function openInsertRowModal() {
      const select = document.getElementById('insert-tbl-select');
      const tables = Object.keys(currentSchema);
      if (tables.length === 0) return alert('No tables available. Create a table or click "Load Sample Data" first.');
      select.innerHTML = tables.map(t => `<option value="${t}">${t}</option>`).join('');
      renderInsertFormFields();
      document.getElementById('insert-row-modal').style.display = 'flex';
    }

    function openInsertRowForTable(tbl) {
      openInsertRowModal();
      document.getElementById('insert-tbl-select').value = tbl;
      renderInsertFormFields();
    }

    function renderInsertFormFields() {
      const tbl = document.getElementById('insert-tbl-select').value;
      const cols = currentSchema[tbl] || [];
      const container = document.getElementById('insert-fields-container');
      container.innerHTML = cols.map(c => `
        <div style="margin-bottom: 8px;">
          <label style="font-size: 11px; font-weight: 600; color: var(--text-muted);">${c}</label>
          <input type="text" class="form-input insert-val" data-col="${c}" placeholder="Enter ${c}...">
        </div>
      `).join('');
    }

    async function submitInsertRow() {
      const tbl = document.getElementById('insert-tbl-select').value;
      const inputs = document.querySelectorAll('.insert-val');
      const rowData = {};
      inputs.forEach(i => {
        const col = i.getAttribute('data-col');
        const val = i.value.trim();
        if (val) rowData[col] = val;
      });

      if (Object.keys(rowData).length === 0) return alert('Please enter at least one field value.');

      try {
        const res = await fetch('/api/insert_row', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ engine: currentEngine, table_name: tbl, data: rowData })
        });
        const data = await res.json();
        if (data.error) alert('Error: ' + data.error);
        else {
          closeModals();
          selectTable(tbl);
        }
      } catch (err) {
        alert('Failed: ' + err);
      }
    }

    function toggleTheme() {
      const current = document.documentElement.getAttribute('data-theme');
      document.documentElement.setAttribute('data-theme', current === 'obsidian' ? 'daylight' : 'obsidian');
    }

    function escapeHtml(str) {
      return (str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
  </script>
</body>
</html>"""


class StudioRequestHandler(http.server.BaseHTTPRequestHandler):
    """Custom HTTP handler for SQLCLI Studio API & Static UI."""

    engine_manager: MultiEngineManager | None = None

    def log_message(self, format: str, *args: Any) -> None:
        pass  # Suppress default console noise

    def _send_json(self, data: Any, status: int = 200) -> None:
        payload = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in {"/", "/index.html"}:
            body = get_dashboard_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/schema":
            qs = urllib.parse.parse_qs(parsed.query)
            engine = qs.get("engine", ["sqlite"])[0]
            schema = self.engine_manager.get_schema(engine) if self.engine_manager else {}
            self._send_json(schema)
            return

        if path == "/api/history":
            history = self.engine_manager.load_history(50) if self.engine_manager else []
            self._send_json(history)
            return

        if path == "/api/saved":
            queries = load_queries()
            self._send_json(queries)
            return

        if path == "/api/topics":
            topics_data = {
                k: {"name": t.name, "category": t.category, "example": t.example, "syntax": t.syntax}
                for k, t in TOPICS.items()
            }
            self._send_json(topics_data)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length)
        body = json.loads(raw_body.decode("utf-8")) if raw_body else {}

        if path == "/api/execute":
            engine = body.get("engine", "sqlite")
            query = body.get("query", "").strip()
            if not self.engine_manager:
                self._send_json({"error": "Engine manager not initialized"}, status=500)
                return

            headers, rows, count, elapsed_ms, error = self.engine_manager.execute(query, engine)
            if error:
                diag = analyze_error(query, error, self.engine_manager.get_schema(engine), engine=engine)
                diag_dict = {
                    "error_type": diag.error_type,
                    "error_code": diag.error_code,
                    "line_number": diag.line_number,
                    "column_offset": diag.column_offset,
                    "faulty_snippet": diag.faulty_snippet,
                    "message": diag.message,
                    "explanation": diag.explanation,
                    "suggested_fix": diag.suggested_fix,
                    "corrected_sql": diag.corrected_sql,
                }
                self._send_json({
                    "error": error,
                    "elapsed_ms": elapsed_ms,
                    "diagnostics": diag_dict,
                })
            else:
                self._send_json({
                    "headers": headers,
                    "rows": rows,
                    "count": count,
                    "elapsed_ms": elapsed_ms,
                    "error": None,
                })
            return

        if path == "/api/demo":
            engine = body.get("engine", "sqlite")
            msg = self.engine_manager.load_sample_data(engine) if self.engine_manager else "Sample data loaded."
            self._send_json({"success": True, "message": msg})
            return

        if path == "/api/create_table":
            engine = body.get("engine", "sqlite")
            table_name = body.get("table_name", "").strip()
            columns = body.get("columns", [])
            if not table_name or not columns:
                self._send_json({"error": "Table name and at least one column are required"}, status=400)
                return
            col_defs = []
            for col in columns:
                name = col.get("name", "").strip()
                col_type = col.get("type", "TEXT").upper()
                pk = " PRIMARY KEY" if col.get("pk") else ""
                auto = ""
                if col.get("pk") and "INT" in col_type:
                    auto = " AUTOINCREMENT" if engine == "sqlite" else " AUTO_INCREMENT"
                col_defs.append(f"`{name}` {col_type}{pk}{auto}")
            sql = f"CREATE TABLE `{table_name}` (\n  " + ",\n  ".join(col_defs) + "\n);"
            headers, rows, count, elapsed_ms, error = self.engine_manager.execute(sql, engine)
            if error:
                self._send_json({"error": error, "sql": sql}, status=400)
            else:
                self._send_json({"success": True, "sql": sql, "message": f"Table '{table_name}' created successfully!"})
            return

        if path == "/api/insert_row":
            engine = body.get("engine", "sqlite")
            table_name = body.get("table_name", "").strip()
            row_data = body.get("data", {})
            if not table_name or not row_data:
                self._send_json({"error": "Table name and row data are required"}, status=400)
                return
            if engine == "nosql":
                new_id = self.engine_manager.nosql.insert(table_name, row_data)
                self._send_json({"success": True, "id": new_id, "message": f"Inserted document #{new_id} into '{table_name}'"})
                return
            cols = [f"`{k}`" for k in row_data.keys()]
            safe_vals = []
            for v in row_data.values():
                if v is None or v == "":
                    safe_vals.append("NULL")
                elif isinstance(v, (int, float)):
                    safe_vals.append(str(v))
                else:
                    esc = str(v).replace("'", "''")
                    safe_vals.append(f"'{esc}'")
            sql = f"INSERT INTO `{table_name}` ({', '.join(cols)}) VALUES ({', '.join(safe_vals)});"
            headers, rows, count, elapsed_ms, error = self.engine_manager.execute(sql, engine)
            if error:
                self._send_json({"error": error, "sql": sql}, status=400)
            else:
                self._send_json({"success": True, "sql": sql, "message": f"Row inserted into '{table_name}'!"})
            return

        if path == "/api/autopilot":
            goal = body.get("goal", "")
            engine = body.get("engine", "sqlite")
            db_ctx = (
                self.engine_manager.mysql
                if (self.engine_manager and engine == "mysql")
                else (self.engine_manager.get_schema(engine) if self.engine_manager else None)
            )
            sql, category, explanation = generate_autopilot_plan(
                goal,
                db_ctx,
                self.engine_manager.settings if self.engine_manager else None,
                engine=engine,
            )
            self._send_json({"sql": sql, "category": category, "explanation": explanation})
            return

        if path == "/api/saved":
            name = body.get("name", "")
            sql = body.get("sql", "")
            if name and sql:
                save_query(name, sql)
                self._send_json({"success": True})
            else:
                self._send_json({"error": "Invalid name or sql"}, status=400)
            return

        self.send_response(404)
        self.end_headers()


def start_studio_server(engine_manager: MultiEngineManager, port: int = 8080, open_browser: bool = False) -> tuple[threading.Thread, int]:
    """Start local Studio Web Dashboard server in a background thread."""
    handler_class = StudioRequestHandler
    handler_class.engine_manager = engine_manager

    server = None
    active_port = port
    for p in range(port, port + 10):
        try:
            server = socketserver.TCPServer(("127.0.0.1", p), handler_class)
            active_port = p
            break
        except OSError:
            continue

    if not server:
        raise RuntimeError(f"Could not bind dashboard server on ports {port}-{port+9}.")

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    url = f"http://localhost:{active_port}"
    if open_browser:
        webbrowser.open(url)

    return thread, active_port


if __name__ == "__main__":
    from .config import load_settings
    from .connection import Database

    settings = load_settings()
    db = Database(settings)
    manager = MultiEngineManager(settings, db)
    _, active_p = start_studio_server(manager, port=8080, open_browser=True)
    print(f"\nSQLCLI Studio Dashboard running at http://localhost:{active_p}")
    print("Press Ctrl+C to stop.\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping dashboard.")
        manager.close()
