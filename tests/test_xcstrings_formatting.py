from localizerx.io.xcstrings import read_xcstrings, write_xcstrings


def test_preserve_xcstrings_formatting(tmp_path):
    # Create a xcstrings file with custom formatting (space before colon)
    content = """{
  "sourceLanguage" : "en",
  "strings" : {
    "test_key" : {
      "extractionState" : "manual",
      "localizations" : {
        "en" : {
          "stringUnit" : {
            "state" : "translated",
            "value" : "Test Value"
          }
        }
      }
    }
  },
  "version" : "1.0"
}
"""
    path = tmp_path / "test.xcstrings"
    path.write_text(content)

    # Read the file
    catalog = read_xcstrings(path)

    # Write it back
    output_path = tmp_path / "output.xcstrings"
    write_xcstrings(catalog, output_path)

    # Check the output
    output_content = output_path.read_text()

    # If the formatting is preserved, it should contain " : "
    assert '"sourceLanguage" : "en"' in output_content
    assert '"strings" : {' in output_content
    assert '"test_key" : {' in output_content


def test_standard_formatting(tmp_path):
    # Create a xcstrings file with standard formatting
    content = """{
  "sourceLanguage": "en",
  "strings": {
    "test_key": {
      "localizations": {
        "en": {
          "stringUnit": {
            "state": "translated",
            "value": "Test Value"
          }
        }
      }
    }
  },
  "version": "1.0"
}
"""
    path = tmp_path / "standard.xcstrings"
    path.write_text(content)

    catalog = read_xcstrings(path)
    output_path = tmp_path / "output_standard.xcstrings"
    write_xcstrings(catalog, output_path)

    output_content = output_path.read_text()

    # Check that standard formatting is preserved (no extra space before colon)
    assert '"sourceLanguage": "en"' in output_content
    assert '"strings": {' in output_content


def test_4_space_indentation(tmp_path):
    # Create a xcstrings file with 4-space indentation
    content = """{
    "sourceLanguage": "en",
    "strings": {
        "test_key": {
            "localizations": {
                "en": {
                    "stringUnit": {
                        "state": "translated",
                        "value": "Test Value"
                    }
                }
            }
        }
    },
    "version": "1.0"
}
"""
    path = tmp_path / "indent4.xcstrings"
    path.write_text(content)

    catalog = read_xcstrings(path)
    output_path = tmp_path / "output_indent4.xcstrings"
    write_xcstrings(catalog, output_path)

    output_content = output_path.read_text()

    # Check for 4-space indentation (4 spaces before "sourceLanguage")
    assert '    "sourceLanguage": "en"' in output_content
    # Check for 8-space indentation (2 levels)
    assert '        "test_key": {' in output_content


def test_triple_space_separator(tmp_path):
    # Create a xcstrings file with triple spaces before/after colon
    content = """{
  "sourceLanguage"   :   "en",
  "strings": {}
}
"""
    path = tmp_path / "triple.xcstrings"
    path.write_text(content)

    catalog = read_xcstrings(path)
    output_path = tmp_path / "output_triple.xcstrings"
    write_xcstrings(catalog, output_path)

    output_content = output_path.read_text()

    # Check that triple spaces are preserved
    assert '"sourceLanguage"   :   "en"' in output_content
