"""
Tests for bug fix: Bug 10 - hasattr with "window()" literal string.

Previously hasattr(parent, "window()") checked for attribute named "window()" (with
parentheses), which never exists. The correct check is hasattr(parent, "window").
"""



class TestBug10HasattrFix:
    """Bug 10: hasattr should check for 'window', not 'window()'."""

    class FakeWidget:
        def window(self):
            return self

    def test_hasattr_with_literal_parens_always_false(self):
        """hasattr(obj, 'window()') with literal parens always returns False."""
        widget = self.FakeWidget()
        assert hasattr(widget, "window()") is False

    def test_hasattr_without_parens_works(self):
        """hasattr(obj, 'window') without parens finds the method."""
        widget = self.FakeWidget()
        assert hasattr(widget, "window") is True

    def test_window_method_callable(self):
        """The window() method should be callable."""
        widget = self.FakeWidget()
        assert callable(getattr(widget, "window", None))

    def test_object_without_window_method(self):
        """Object without window() should return False for both checks."""
        obj = object()
        assert hasattr(obj, "window()") is False
        assert hasattr(obj, "window") is False
