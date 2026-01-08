"""Tests for the reference manager module."""

import time
import pytest

from linux_desktop_mcp.references import (
    ElementReference,
    ElementRole,
    ElementBounds,
    ElementState,
    ReferenceManager,
)


class TestElementBounds:
    """Tests for ElementBounds class."""

    def test_center_calculation(self):
        """Test center point calculation."""
        bounds = ElementBounds(x=100, y=200, width=50, height=30)
        assert bounds.center == (125, 215)

    def test_is_valid_positive(self):
        """Test valid bounds detection."""
        bounds = ElementBounds(x=0, y=0, width=100, height=100)
        assert bounds.is_valid is True

    def test_is_valid_zero_width(self):
        """Test invalid bounds with zero width."""
        bounds = ElementBounds(x=0, y=0, width=0, height=100)
        assert bounds.is_valid is False

    def test_is_valid_zero_height(self):
        """Test invalid bounds with zero height."""
        bounds = ElementBounds(x=0, y=0, width=100, height=0)
        assert bounds.is_valid is False

    def test_is_valid_negative_x(self):
        """Test invalid bounds with negative x."""
        bounds = ElementBounds(x=-1, y=0, width=100, height=100)
        assert bounds.is_valid is False

    def test_is_valid_negative_y(self):
        """Test invalid bounds with negative y."""
        bounds = ElementBounds(x=0, y=-1, width=100, height=100)
        assert bounds.is_valid is False

    def test_is_valid_overflow_width(self):
        """Test invalid bounds with overflow width."""
        bounds = ElementBounds(x=0, y=0, width=70000, height=100)
        assert bounds.is_valid is False

    def test_contains_point_inside(self):
        """Test point containment for point inside bounds."""
        bounds = ElementBounds(x=100, y=100, width=50, height=50)
        assert bounds.contains_point(125, 125) is True

    def test_contains_point_outside(self):
        """Test point containment for point outside bounds."""
        bounds = ElementBounds(x=100, y=100, width=50, height=50)
        assert bounds.contains_point(50, 50) is False

    def test_contains_point_edge(self):
        """Test point containment for point on edge."""
        bounds = ElementBounds(x=100, y=100, width=50, height=50)
        assert bounds.contains_point(100, 100) is True
        assert bounds.contains_point(149, 149) is True
        assert bounds.contains_point(150, 150) is False


class TestElementState:
    """Tests for ElementState class."""

    def test_to_list_empty(self):
        """Test to_list with default state."""
        state = ElementState()
        assert state.to_list() == []

    def test_to_list_focused(self):
        """Test to_list with focused state."""
        state = ElementState(focused=True)
        assert "focused" in state.to_list()

    def test_to_list_disabled(self):
        """Test to_list with disabled state."""
        state = ElementState(enabled=False)
        assert "disabled" in state.to_list()

    def test_to_list_hidden(self):
        """Test to_list with hidden state."""
        state = ElementState(visible=False)
        assert "hidden" in state.to_list()

    def test_to_list_multiple_states(self):
        """Test to_list with multiple states."""
        state = ElementState(focused=True, editable=True, checked=True)
        states = state.to_list()
        assert "focused" in states
        assert "editable" in states
        assert "checked" in states


class TestElementReference:
    """Tests for ElementReference class."""

    def create_ref(self, **kwargs) -> ElementReference:
        """Create a test reference with default values."""
        defaults = {
            "ref_id": "ref_1",
            "source": "atspi",
            "role": ElementRole.BUTTON,
            "name": "Test Button",
            "bounds": ElementBounds(x=0, y=0, width=100, height=30),
            "state": ElementState(),
        }
        defaults.update(kwargs)
        return ElementReference(**defaults)

    def test_matches_query_by_name(self):
        """Test query matching by element name."""
        ref = self.create_ref(name="Save Button")
        assert ref.matches_query("save") is True
        assert ref.matches_query("button") is True
        assert ref.matches_query("delete") is False

    def test_matches_query_by_role(self):
        """Test query matching by element role."""
        ref = self.create_ref(role=ElementRole.BUTTON)
        assert ref.matches_query("button") is True

    def test_matches_query_by_description(self):
        """Test query matching by description."""
        ref = self.create_ref(description="Saves the document")
        assert ref.matches_query("document") is True

    def test_format_for_display(self):
        """Test display formatting."""
        ref = self.create_ref(name="Test", role=ElementRole.BUTTON)
        formatted = ref.format_for_display()
        assert "ref_1" in formatted
        assert "[button]" in formatted
        assert '"Test"' in formatted


class TestReferenceManager:
    """Tests for ReferenceManager class."""

    def create_ref(self, ref_id: str, name: str = "Test") -> ElementReference:
        """Create a test reference."""
        return ElementReference(
            ref_id=ref_id,
            source="atspi",
            role=ElementRole.BUTTON,
            name=name,
            bounds=ElementBounds(x=0, y=0, width=100, height=30),
            state=ElementState(),
        )

    def test_add_and_get(self):
        """Test adding and retrieving references."""
        manager = ReferenceManager()
        ref = self.create_ref("ref_1")
        manager.add(ref)
        retrieved = manager.get("ref_1")
        assert retrieved is not None
        assert retrieved.ref_id == "ref_1"

    def test_get_nonexistent(self):
        """Test getting a nonexistent reference."""
        manager = ReferenceManager()
        assert manager.get("ref_999") is None

    def test_generate_ref_id(self):
        """Test reference ID generation."""
        manager = ReferenceManager()
        id1 = manager.generate_ref_id()
        id2 = manager.generate_ref_id()
        assert id1 != id2
        assert id1.startswith("ref_")
        assert id2.startswith("ref_")

    def test_clear(self):
        """Test clearing all references."""
        manager = ReferenceManager()
        manager.add(self.create_ref("ref_1"))
        manager.add(self.create_ref("ref_2"))
        manager.clear()
        assert len(manager) == 0

    def test_find_by_name(self):
        """Test finding references by name."""
        manager = ReferenceManager()
        manager.add(self.create_ref("ref_1", name="Save Button"))
        manager.add(self.create_ref("ref_2", name="Cancel Button"))
        manager.add(self.create_ref("ref_3", name="Submit"))

        results = manager.find_by_name("button")
        assert len(results) == 2

    def test_find_by_query(self):
        """Test finding references by query."""
        manager = ReferenceManager()
        manager.add(self.create_ref("ref_1", name="Save"))
        manager.add(self.create_ref("ref_2", name="Cancel"))

        results = manager.find_by_query("save")
        assert len(results) == 1
        assert results[0].name == "Save"

    def test_ttl_expiration(self):
        """Test that references expire after TTL."""
        manager = ReferenceManager(ttl=0.1)  # 100ms TTL
        ref = self.create_ref("ref_1")
        manager.add(ref)

        # Should exist immediately
        assert manager.get("ref_1") is not None

        # Wait for expiration
        time.sleep(0.15)

        # Should be expired now
        assert manager.get("ref_1") is None

    def test_gc_interval(self):
        """Test that GC runs periodically."""
        manager = ReferenceManager(ttl=0.1)
        manager.GC_INTERVAL = 0.05  # 50ms GC interval

        manager.add(self.create_ref("ref_1"))
        manager.add(self.create_ref("ref_2"))

        # Wait for TTL and GC
        time.sleep(0.2)

        # Trigger GC via get
        manager.get("ref_nonexistent")

        assert len(manager) == 0
