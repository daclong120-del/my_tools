Đúng, bạn nói đúng. Sửa lại cho đầy đủ:

## 3 nhân viên (3 Stream)

**Nhân viên 1 — Scraper** (1 người / tab)
> Lật trang SocialPeta → bắt quảng cáo → nếu YouTube thì dừng tìm link → lật trang tiếp

**Nhân viên 2 — Downloader** (nhiều người)
> Ngồi chờ có link → tải file về

**Nhân viên 3 — Dedup** (1 người)
> File tải xong → kiểm tra trùng lặp 3 bước: so thời lượng → so audio → so hình ảnh. Trùng thì xóa, không trùng thì giữ.

---

### Dòng chảy đơn giản:

```
Scraper bắt quảng cáo
    ↓
Downloader tải file
    ↓
Dedup kiểm tra trùng → giữ hoặc xóa
```

Ba cái này chạy **song song**, không chờ nhau (trừ YouTube extraction bắt buộc chờ như đã nói ở trên).

Lần trước tôi bỏ sót nhân viên Dedup — lỗi của AI agent kia khi giải thích lần đầu, nó cũng quên luôn cho đến khi bạn nhắc.