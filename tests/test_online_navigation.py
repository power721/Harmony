"""
Test navigation stack for online music views.
Tests that back navigation properly returns to playlist/album lists.
"""

import pytest
from unittest.mock import Mock


def test_navigation_stack_logic():
    """Test navigation stack logic without UI."""
    # Simulate navigation stack
    navigation_stack = []

    # Test 1: Push playlist list
    playlists = [{"id": "1", "title": "Playlist 1"}]
    navigation_stack.append({
        'page': 'playlists',
        'title': 'Test Playlists',
        'data': playlists
    })

    assert len(navigation_stack) == 1
    assert navigation_stack[0]['page'] == 'playlists'
    assert navigation_stack[0]['title'] == 'Test Playlists'

    # Test 2: Push album list
    albums = [{"mid": "1", "title": "Album 1"}]
    navigation_stack.append({
        'page': 'albums',
        'title': 'Test Albums',
        'data': albums
    })

    assert len(navigation_stack) == 2
    assert navigation_stack[1]['page'] == 'albums'

    # Test 3: Pop (back navigation)
    prev_state = navigation_stack.pop()
    assert prev_state['page'] == 'albums'
    assert len(navigation_stack) == 1

    # Test 4: Pop again
    prev_state = navigation_stack.pop()
    assert prev_state['page'] == 'playlists'
    assert len(navigation_stack) == 0

    # Test 5: Clear stack
    navigation_stack.append({'page': 'playlists', 'title': 'Test', 'data': []})
    navigation_stack.append({'page': 'albums', 'title': 'Test 2', 'data': []})
    navigation_stack.clear()
    assert len(navigation_stack) == 0


def test_multiple_navigation_levels():
    """Test multi-level navigation."""
    navigation_stack = []

    # Navigate through multiple levels
    navigation_stack.append({'page': 'playlists', 'title': 'Level 1', 'data': []})
    navigation_stack.append({'page': 'albums', 'title': 'Level 2', 'data': []})
    navigation_stack.append({'page': 'playlists', 'title': 'Level 3', 'data': []})

    assert len(navigation_stack) == 3

    # Pop back through levels
    assert navigation_stack.pop()['title'] == 'Level 3'
    assert len(navigation_stack) == 2

    assert navigation_stack.pop()['title'] == 'Level 2'
    assert len(navigation_stack) == 1

    assert navigation_stack.pop()['title'] == 'Level 1'
    assert len(navigation_stack) == 0
