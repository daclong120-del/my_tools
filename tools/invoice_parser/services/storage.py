import os
import shutil

class StorageService:
    def __init__(self, upload_dir: str):
        self.upload_dir = upload_dir
        os.makedirs(self.upload_dir, exist_ok=True)

    def save_file(self, filename: str, file_content: bytes) -> str:
        # Luu file vao thu muc uploads
        file_path = os.path.join(self.upload_dir, filename)
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)
        return file_path

    def delete_file(self, filename: str) -> bool:
        file_path = os.path.join(self.upload_dir, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
