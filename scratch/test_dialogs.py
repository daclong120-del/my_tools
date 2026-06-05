import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Thêm tools vào sys.path để import đúng module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools")))

class TestDialogs(unittest.TestCase):
    @patch('tkinter.Tk')
    @patch('tkinter.filedialog.askdirectory')
    def test_select_directory_success(self, mock_askdirectory, mock_tk):
        from socialpeta_downloader.core.utils import select_directory

        # Giả lập askdirectory trả về một đường dẫn hợp lệ
        expected_path = os.path.abspath("d:/Python/my_tools/data")
        mock_askdirectory.return_value = expected_path

        # Giả lập đối tượng Tk root
        mock_root = MagicMock()
        mock_tk.return_value = mock_root

        # Gọi hàm cần test
        result = select_directory(initial_dir="d:/Python/my_tools/data", title="Test Directory")

        # Kiểm tra kết quả
        self.assertEqual(result, expected_path)

        # Kiểm tra xem các phương thức của Tkinter có được gọi đúng quy trình không
        mock_tk.assert_called_once()
        mock_root.withdraw.assert_called_once()
        mock_root.wm_attributes.assert_called_with("-topmost", 1)
        mock_askdirectory.assert_called_once_with(
            parent=mock_root,
            title="Test Directory",
            initialdir="d:/Python/my_tools/data"
        )
        mock_root.destroy.assert_called_once()

    @patch('tkinter.Tk')
    @patch('tkinter.filedialog.askdirectory')
    def test_select_directory_cancel(self, mock_askdirectory, mock_tk):
        from socialpeta_downloader.core.utils import select_directory

        # Giả lập askdirectory trả về chuỗi rỗng (khi người dùng hủy bỏ)
        mock_askdirectory.return_value = ""

        mock_root = MagicMock()
        mock_tk.return_value = mock_root

        result = select_directory()

        # Kết quả trả về phải là None
        self.assertIsNone(result)
        mock_root.destroy.assert_called_once()

    @patch('tkinter.Tk')
    @patch('tkinter.filedialog.askopenfilename')
    def test_select_file_success(self, mock_askopenfilename, mock_tk):
        from socialpeta_downloader.core.utils import select_file

        expected_file = os.path.abspath("d:/Python/my_tools/data/config.json")
        mock_askopenfilename.return_value = expected_file

        mock_root = MagicMock()
        mock_tk.return_value = mock_root

        result = select_file(title="Test File", filetypes=[("JSON Files", "*.json")])

        self.assertEqual(result, expected_file)
        mock_tk.assert_called_once()
        mock_root.withdraw.assert_called_once()
        mock_root.wm_attributes.assert_called_with("-topmost", 1)
        mock_askopenfilename.assert_called_once_with(
            parent=mock_root,
            title="Test File",
            initialdir=os.getcwd(),
            filetypes=[("JSON Files", "*.json")]
        )
        mock_root.destroy.assert_called_once()

    @patch('tkinter.Tk')
    @patch('tkinter.filedialog.askopenfilename')
    def test_select_file_cancel(self, mock_askopenfilename, mock_tk):
        from socialpeta_downloader.core.utils import select_file

        mock_askopenfilename.return_value = ""

        mock_root = MagicMock()
        mock_tk.return_value = mock_root

        result = select_file()

        self.assertIsNone(result)
        mock_root.destroy.assert_called_once()

if __name__ == '__main__':
    unittest.main()
