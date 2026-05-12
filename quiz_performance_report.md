# Performance Testing Report — Moodle Cloud (Quiz Attempt)

## 1. Thông tin chung

| Mục | Chi tiết |
|---|---|
| **Loại test** | Performance Testing (Non-Functional) |
| **Tool** | Locust 2.44.0 |
| **Target URL** | https://tuanemtramtinh.moodlecloud.com/mod/quiz/view.php?id=63 |
| **Tài khoản** | chaonhom / sApTOIhanNopDA05 |
| **Thời gian chạy** | 3 phút |
| **Ngày thực hiện** | 2026-05-12 |

---

## 2. Mục tiêu kiểm thử

> *"Response times and throughput rates under certain workload and configuration conditions. Test cases are designed to show that the program does not satisfy its performance objectives."*

Kiểm tra hệ thống Moodle Cloud có đáp ứng được yêu cầu hiệu năng khi **nhiều người dùng đồng thời truy cập và bắt đầu làm bài quiz** hay không.

**Chức năng được test:** Xem quiz và bắt đầu làm bài (`mod/quiz/view.php?id=63` → `startattempt.php`)

Tương đương test case **TC002003** (no-password quiz): click "Attempt quiz now" → xác nhận redirect đến `attempt.php`.

Luồng thực hiện của mỗi virtual user:

| Bước | Hành động | Endpoint |
|---|---|---|
| 1 | Đăng nhập (lấy CSRF logintoken) | `GET /login/index.php` |
| 2 | Xác thực tài khoản | `POST /login/index.php` |
| 3 | Mở trang xem quiz | `GET /mod/quiz/view.php?id=63` |
| 4 | Bắt đầu làm bài (click "Attempt quiz now") | `POST /mod/quiz/startattempt.php` |
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
| Tổng request | 868 | — | — |
| Tổng lỗi | 69 | — | — |
| **Failure Rate** | **7.95%** | < 5% | **FAIL** |
| **P95 Response Time** | **19000 ms** | < 3000 ms | **FAIL** |
| **Throughput** | **4.68 req/s** | >= 5 req/s | **FAIL** |

---

## 6. Chi tiết từng endpoint

| Endpoint | Requests | Failures | Failure Rate | Median | P95 | Max |
|---|---|---|---|---|---|---|
| GET /mod/quiz/view.php?id=63 | 366 | 38 | 10.4% | 1200 ms | 9500 ms | 28355 ms |
| POST /mod/quiz/startattempt.php | 355 | 31 | 8.7% | 1600 ms | 16000 ms | 42664 ms |
| GET /login (token fetch) | 50 | 0 | 0% | 7200 ms | 29000 ms | 29774 ms |
| POST /login | 50 | 0 | 0% | 4300 ms | 35000 ms | 35651 ms |
| GET /logout | 47 | 0 | 0% | 2900 ms | 4100 ms | 4554 ms |

> **Ghi chú:** Login/logout có response time cao do chúng xảy ra đồng thời khi 50 users bắt đầu spawn trong Stage 3. Các endpoint này không bị tính là failure (không áp dụng SLO check).

---

## 7. Phân tích theo từng giai đoạn tải

### Stage 1 — 5 users (0–60 giây): Bình thường
- Response time ổn định trong khoảng **809–2600 ms**
- Không có lỗi (0 failures)
- Throughput: ~1.4–2.0 req/s
- P95: ~2600 ms — **tiệm cận ngưỡng SLO nhưng chưa vượt**
- Hệ thống hoạt động bình thường với tải nhỏ

### Stage 2 — 20 users (60–120 giây): Ổn định, đáp ứng tốt
- Response time: **1300–2800 ms**
- Không có lỗi (0 failures)
- Throughput tăng lên **6–8.3 req/s** — vượt SLO tối thiểu
- P95: ~2000–2800 ms — trong ngưỡng SLO
- Hệ thống chịu tải tốt ở 20 users

### Stage 3 — 50 users (120–180 giây): Vượt ngưỡng
- Lỗi xuất hiện ngay từ giây thứ **~123** (ngay khi 50 users hit)
- P95 tăng vọt: **2800 ms → 9500 ms → 19000 ms → 42000 ms**
- Failure rate tăng nhanh từ 0% đến **7.95%** (tổng cộng)
- Throughput không ổn định: dao động 1.7–14.3 req/s, trung bình **4.68 req/s** (dưới SLO)
- Hệ thống **không đáp ứng** được tải ở mức 50 users đồng thời

---

## 8. Phân loại lỗi

| Loại lỗi | Số lần | Endpoint bị ảnh hưởng |
|---|---|---|
| Response quá chậm (> 3000 ms) | 69 | GET view (38), POST startattempt (31) |
| HTTP 500 — Server Error | 0 | — |
| HTTP 404 — Not Found | 0 | — |

**Điểm đáng chú ý:**
- **Toàn bộ 69 lỗi đều là "quá chậm"** — không có HTTP 500 hay 404. MoodleCloud không bị crash, chỉ bị quá tải dẫn đến response time vượt SLO
- Max response time lên đến **42664 ms (~43 giây)** tại `POST /mod/quiz/startattempt.php`
- `GET /mod/quiz/view.php?id=63` chậm nhất là **28355 ms (~28 giây)**

---

## 9. Kết luận

> Hệ thống **KHÔNG đáp ứng** performance objectives khi có **50 users đồng thời** truy cập và bắt đầu làm bài quiz.

| Mức tải | Failure Rate | P95 | Throughput | Kết quả |
|---|---|---|---|---|
| 5 users | 0% | ~2600 ms | ~1.7 req/s | Hoạt động tốt, P95 tiệm cận ngưỡng |
| 20 users | 0% | ~2800 ms | ~6–8 req/s | Đáp ứng SLO, hệ thống ổn định |
| 50 users | **7.95%** | **19000 ms** | **4.68 req/s** | **Vượt ngưỡng — FAIL** |

- **Điểm gãy (breaking point):** ~50 concurrent users
- **P95:** Vượt SLO gấp **6.3 lần** (19000 ms vs 3000 ms)
- **Failure Rate:** Vượt SLO gấp **1.6 lần** (7.95% vs 5%)
- **Throughput:** Không đạt SLO (4.68 req/s < 5 req/s)
- **Chức năng đăng nhập:** Không có lỗi, nhưng response time cao (median 4300–7200 ms) do tranh chấp tài nguyên khi 50 users spawn đồng thời

Kết quả này đúng với mục tiêu của performance testing: **chứng minh hệ thống không đáp ứng được performance objectives** khi tải vượt ngưỡng cho phép.
