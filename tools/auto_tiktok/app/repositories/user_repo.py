# Giả lập Database trong bộ nhớ cho khung thô chạy thử nghiệm
class UserMockDB:
    users = []
    counter = 0

class UserRepo:
    @staticmethod
    async def get_by_email(email: str):
        # Chỉ query DB tìm kiếm user
        for user in UserMockDB.users:
            if user["email"] == email:
                return user
        return None

    @staticmethod
    async def insert(name: str, email: str, hashed_pw: str):
        # Chỉ lo thao tác ghi/đọc DB, không có logic nghiệp vụ
        UserMockDB.counter += 1
        new_user = {
            "id": UserMockDB.counter,
            "name": name,
            "email": email,
            "password": hashed_pw
        }
        UserMockDB.users.append(new_user)
        return new_user
