import io
import sys
import unittest

class MockCharmapStream:
    """
    A mock stream that simulates a Windows stream with a limited encoding (like cp1252/charmap).
    It throws UnicodeEncodeError when attempting to write characters it cannot represent.
    """
    def __init__(self):
        self.buffer = io.BytesIO()
        self.text_content = ""

    def write(self, data):
        # cp1252 cannot encode Vietnamese character 'ắ' (\u1eaf)
        # We simulate this behavior:
        data.encode('cp1252')
        self.text_content += data

    def flush(self):
        pass


class SafeStreamWrapper:
    def __init__(self, original_stream):
        self.original_stream = original_stream

    def write(self, data):
        if not self.original_stream:
            return
        try:
            self.original_stream.write(data)
        except UnicodeEncodeError:
            try:
                if hasattr(self.original_stream, 'buffer'):
                    # In real streams, we write UTF-8 to the buffer
                    self.original_stream.buffer.write(data.encode('utf-8'))
                else:
                    self.original_stream.write(data.encode('ascii', errors='backslashreplace').decode('ascii'))
            except Exception:
                try:
                    self.original_stream.write(data.encode('ascii', errors='ignore').decode('ascii'))
                except Exception:
                    pass

    def flush(self):
        if self.original_stream and hasattr(self.original_stream, 'flush'):
            try:
                self.original_stream.flush()
            except Exception:
                pass

    def __getattr__(self, name):
        return getattr(self.original_stream, name)


class TestSafeStream(unittest.TestCase):
    def test_unicode_encode_fallback_without_buffer(self):
        mock_stream = MockCharmapStream()
        # Remove buffer to test fallback without buffer
        del mock_stream.buffer
        
        wrapped = SafeStreamWrapper(mock_stream)
        
        # This string contains 'ắ' (\u1eaf), which cannot be encoded in cp1252
        test_str = "Bắt đầu tải xuống"
        
        # Running write on raw MockCharmapStream should fail
        with self.assertRaises(UnicodeEncodeError):
            mock_stream.write(test_str)
            
        # Running write on wrapped stream should NOT fail
        try:
            wrapped.write(test_str)
        except Exception as e:
            self.fail(f"SafeStreamWrapper raised an exception: {e}")
            
        # The character '\u1eaf' should be replaced with its backslash escaped form
        self.assertIn("B\\u1eaft \\u0111\\u1ea7u t\\u1ea3i xu\\u1ed1ng", mock_stream.text_content)

    def test_unicode_encode_with_buffer(self):
        mock_stream = MockCharmapStream()
        wrapped = SafeStreamWrapper(mock_stream)
        
        test_str = "Bắt đầu tải xuống"
        
        # Running write on wrapped stream should NOT fail
        try:
            wrapped.write(test_str)
        except Exception as e:
            self.fail(f"SafeStreamWrapper raised an exception: {e}")
            
        # It should have written the utf-8 encoded bytes to the buffer
        mock_stream.buffer.seek(0)
        buffer_content = mock_stream.buffer.read().decode('utf-8')
        self.assertEqual(buffer_content, test_str)


if __name__ == '__main__':
    unittest.main()
