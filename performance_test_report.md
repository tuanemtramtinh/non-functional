# Performance Testing Report — Moodle Demo

## 1. Thông tin chung

| Mục | Chi tiết |
|---|---|
| **Loại test** | Performance Testing (Non-Functional) |
| **Tool** | Locust 2.44.0 |
| **Target URL** | https://school.moodledemo.net/course/edit.php?category=0 |
| **Tài khoản** | manager / moodle26 |
| **Thời gian chạy** | 3 phút |
| **Ngày thực hiện** | 2026-05-12 |

---

## 2. Mục tiêu kiểm thử

> *"Response times and throughput rates under certain workload and configuration conditions. Test cases are designed to show that the program does not satisfy its performance objectives."*

Kiểm tra hệ thống Moodle có đáp ứng được yêu cầu hiệu năng khi **nhiều người dùng tạo khoá học đồng thời** hay không.

**Chức năng được test:** Tạo khoá học mới (`course/edit.php?category=0`)

Luồng thực hiện của mỗi virtual user:

| Bước | Hành động | Endpoint |
|---|---|---|
| 1 | Đăng nhập (lấy CSRF logintoken) | `GET /login/index.php` |
| 2 | Xác thực tài khoản | `POST /login/index.php` |
| 3 | Mở form tạo khoá học | `GET /course/edit.php?category=0` |
| 4 | Submit tạo khoá học mới | `POST /course/edit.php` |
| 5 | Đăng xuất | `GET /login/logout.php` |

---

## 3. Workload — Mô hình tăng tải (Stair-step)

| Stage | Thời gian | Số users đồng thời | Spawn rate |
|---|---|---|---|
| 1 — Warm-up | 0–60 giây | 5 users | 2 users/s |
| 2 — Tăng tải | 60–120 giây | 20 users | 5 users/s |
| 3 — Stress | 120–180 giây | 50 users | 10 users/s |

---

## 4. Performance Objectives (SLOs)

| Chỉ số | Ngưỡng yêu cầu |
|---|---|
| P95 Response Time | < 3000 ms |
| Failure Rate | < 5% |
| Throughput | >= 5 req/s |

---

## 5. Kết quả tổng quan

| Chỉ số | Kết quả thực tế | SLO yêu cầu | Kết luận |
|---|---|---|---|
| Tổng request | 931 | — | — |
| Tổng lỗi | 251 | — | — |
| **Failure Rate** | **26.96%** | < 5% | **FAIL** |
| **P95 Response Time** | **7400 ms** | < 3000 ms | **FAIL** |
| **Throughput** | **5.03 req/s** | >= 5 req/s | PASS |

---

## 6. Chi tiết từng endpoint

| Endpoint | Requests | Failures | Failure Rate | Median | P95 | Max |
|---|---|---|---|---|---|---|
| GET /course/edit.php?category=0 | 417 | 155 | 37.2% | 2200 ms | 7000 ms | 23716 ms |
| POST /course/edit.php (tạo khoá học) | 392 | 96 | 24.5% | 2400 ms | 7600 ms | 9955 ms |
| GET /login (token fetch) | 50 | 0 | 0% | 1700 ms | 3900 ms | 5032 ms |
| POST /login | 50 | 0 | 0% | 4500 ms | 9900 ms | 11025 ms |
| GET /logout | 22 | 0 | 0% | 4300 ms | 4800 ms | 4852 ms |

---

## 7. Phân tích theo từng giai đoạn tải

### Stage 1 — 5 users (0–60 giây): Bình thường
- Response time ổn định trong khoảng **413–1300 ms**
- Hầu như không có lỗi (1 lỗi duy nhất)
- Throughput đạt ~2 req/s
- Hệ thống hoạt động bình thường, đáp ứng tốt SLO

### Stage 2 — 20 users (60–120 giây): Bắt đầu có dấu hiệu chậm
- Response time tăng lên **1000–3300 ms**
- Rất ít lỗi (4 lỗi tổng cộng đến cuối stage)
- Throughput tăng lên ~5–7 req/s
- Hệ thống chịu tải được nhưng response time đang tiệm cận ngưỡng SLO

### Stage 3 — 50 users (120–180 giây): Vượt ngưỡng
- Lỗi bùng phát từ giây thứ ~129
- P95 tăng vọt lên **7400 ms** (vượt SLO gấp 2.5 lần)
- Failure rate tăng nhanh từ <1% đến **26.96%**
- Xuất hiện lỗi HTTP 500 và HTTP 404 — server bắt đầu crash
- Hệ thống không đáp ứng được tải ở mức 50 users đồng thời

---

## 8. Phân loại lỗi

| Loại lỗi | Số lần | Ý nghĩa |
|---|---|---|
| Response quá chậm (> 3000 ms) | ~240 | Server xử lý nhưng quá chậm |
| HTTP 500 — Server Error | 3 | Server bị crash/quá tải |
| HTTP 404 — Not Found | 8 | Resource không tìm thấy do tải cao |
| Form validation error | 1 | Dữ liệu submit không hợp lệ |

**Điểm đáng chú ý so với lần chạy trước:**
- Xuất hiện thêm **HTTP 500** và **HTTP 404** — đây là dấu hiệu server bắt đầu không ổn định, không chỉ đơn thuần là chậm
- Max response time lên đến **23716 ms** (gần 24 giây) tại endpoint GET form

---

## 9. Kết luận

> Hệ thống **KHÔNG đáp ứng** performance objectives khi có **50 users đồng thời** tạo khoá học.

| Mức tải | Failure Rate | P95 | Kết quả |
|---|---|---|---|
| 5 users | ~0.8% | ~1300 ms | Hoạt động tốt, đáp ứng SLO |
| 20 users | ~0.8% | ~3000 ms | Tiệm cận ngưỡng, vẫn chấp nhận được |
| 50 users | **26.96%** | **7400 ms** | **Vượt ngưỡng — FAIL** |

- **Điểm gãy (breaking point):** ~50 concurrent users
- **P95:** Vượt SLO gấp **2.5 lần** (7400 ms vs 3000 ms)
- **Failure Rate:** Vượt SLO gấp **5.4 lần** (26.96% vs 5%)
- **Throughput:** Đạt SLO tối thiểu (5.03 req/s ≥ 5 req/s)
- **Chức năng đăng nhập:** Ổn định hoàn toàn, không có lỗi trong suốt quá trình test

Kết quả này đúng với mục tiêu của performance testing: **chứng minh hệ thống không đáp ứng được performance objectives** khi tải vượt ngưỡng cho phép.
