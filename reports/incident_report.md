# Incident Report

## Severity
P1 — Silent revenue inflation visible on CEO dashboard

## Summary
Daily revenue in `fct_daily_revenue` was inflated up to 2× the true value of completed orders. The root cause was an SCD Type-2 fan-out bug: after a failed dimension refresh, multiple customers had two `is_active = true` rows simultaneously. The `LEFT JOIN` in the mart duplicated each affected order row, silently doubling revenue — no SQL error, no schema change, no alert from the default monitoring stack.

## Detection
- Signal: `assert_daily_revenue_matches_orders` singular dbt test returned rows with `abs_diff > 0.01`; `detect_distribution_shift` reported `score = 2.07, is_anomaly = True` (mean ratio vs 7-day baseline)
- First observed time: During `dbt build` run after fault injection into the customer dimension table (2026-08-30)

## Root Cause
`stg_customers` contained two `is_active = true` rows for the same `customer_id` after an SCD Type-2 update job failed to close the stale row (`valid_to` not set). The original `LEFT JOIN` in `fct_daily_revenue` matched two customer rows per order → two output rows per order → `GROUP BY order_date` summed duplicated `amount_usd` values → revenue inflation.

## Evidence
1. `assert_daily_revenue_matches_orders` failure: 5 dates had `abs_diff` 80–350 USD — exactly 2× the real revenue for those dates.
2. `detect_distribution_shift` returned `score = 2.07` (mean_ratio), `is_anomaly = True`.
3. Manual query `SELECT * FROM stg_customers WHERE customer_id='C0042' AND is_active=true` returned 2 rows — confirmed fan-out source.

## Blast Radius

```text
raw customers table
  -> stg_customers          (is_active=true filter keeps both rows)
       -> fct_daily_revenue  (LEFT JOIN multiplies order rows)
            -> CEO dashboard daily_revenue KPI   [P1 user-visible]
            -> Any downstream model joining fct_daily_revenue
```

## Mitigation
**Immediate:** Updated `fct_daily_revenue.sql` to de-duplicate active customers with `ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY valid_from DESC)` before the JOIN — keeps only the most-recent active row per customer.
**Parallel:** Patched upstream dimension table to set `is_active = false` on stale rows that the SCD job failed to close.

## Recovery
1. Ran `dbt build` with patched model → all 21 tests PASS.
2. `assert_daily_revenue_matches_orders` returns 0 rows → mart reconciles with raw sum.
3. `assert_single_active_customer` returns 0 rows after upstream dimension fix.
4. CEO dashboard refreshed with corrected daily_revenue figures.

## Verification
- [x] Contract healthy — `validate_orders` passes all column checks
- [x] dbt tests healthy — all 21 generic + singular + unit tests pass after patch
- [x] anomaly returned to expected range — distribution score < 1.1
- [x] SLO healthy / budget understood — bad_rate back below target after fix
- [x] downstream output verified — CEO dashboard shows correct values

## Prevention / Action Items
| Action | Owner | Deadline | Why |
|---|---|---|---|
| Add `assert_single_active_customer` to CI blocking gate | Data Engineering | Sprint +1 | Catch SCD fan-out before it reaches prod |
| Add `assert_daily_revenue_matches_orders` as nightly monitor | Data Engineering | Sprint +1 | Revenue reconciliation as safety net |
| Fix SCD job to properly `UPDATE is_active=false` on old rows | Data Engineering | Sprint +1 | Fix root cause, not just symptom |
| Add dbt unit test for fan-out scenario to PR checks | Data Engineering | Sprint +1 | Shift-left: catch at PR time, not prod |
| Add anomaly alert on `daily_revenue` distribution to PagerDuty | Platform | Sprint +2 | Detect drift if reconciliation test is missed |

---
---

# Báo Cáo Sự Cố — Game Day Mystery Incident (Tiếng Việt)

## Mức Độ Nghiêm Trọng
P1 — Dữ liệu doanh thu bị sai lệch, hiển thị trực tiếp trên dashboard của CEO.

## Tóm Tắt

Số liệu doanh thu hàng ngày trong mart `fct_daily_revenue` bị **phình lên gấp đôi** so với tổng thực tế của các đơn hàng đã hoàn thành. Sự cố hoàn toàn im lặng — không có lỗi SQL, không có thay đổi schema, không có cảnh báo từ hệ thống monitoring mặc định.

Nguyên nhân gốc rễ là **lỗi SCD Type-2 fan-out** trong bảng chiều khách hàng: sau một lần refresh thất bại, nhiều khách hàng có **hai dòng `is_active = true`** cùng tồn tại. Câu lệnh `LEFT JOIN` trong mart nhân bản mỗi dòng đơn hàng tương ứng, khiến doanh thu bị tính gấp đôi cho những khách hàng bị ảnh hưởng.

## Phát Hiện

- **Tín hiệu cảnh báo:** Test singular `assert_daily_revenue_matches_orders` trả về các dòng có `abs_diff > 0.01`, chỉ ra tổng trong mart ≠ tổng từ bảng đơn hàng gốc.
- **Tín hiệu bổ sung:** Hàm `detect_distribution_shift` (phiên bản multi-signal) phát hiện tỷ lệ mean ratio > 2× so với baseline 7 ngày — `score = 2.07, is_anomaly = True`.
- **Thời điểm phát hiện đầu tiên:** Trong quá trình chạy `dbt build` sau khi inject lỗi giả lập (fault injection) vào bảng chiều khách hàng.

## Nguyên Nhân Gốc Rễ

Bảng `stg_customers` chứa **hai dòng `is_active = true`** cho cùng một `customer_id` (ví dụ: `C0042`) sau khi job cập nhật SCD Type-2 không đóng đúng dòng cũ:

```
customer_id | is_active | valid_from  | valid_to
C0042       | true      | 2026-01-01  | 2026-07-31   ← lẽ ra phải là false
C0042       | true      | 2026-08-01  | NULL         ← dòng hiện tại đúng
```

Câu SQL gốc trong `fct_daily_revenue.sql`:
```sql
left join active_customers c on o.customer_id = c.customer_id
```
Với mỗi đơn hàng của `C0042`, SQL khớp với **hai dòng** khách hàng → tạo ra **hai dòng kết quả** cho mỗi đơn hàng → `GROUP BY order_date` cộng dồn cả hai giá trị `amount_usd` → doanh thu bị nhân đôi.

## Bằng Chứng

1. Test `assert_daily_revenue_matches_orders` thất bại: 5 ngày có `abs_diff` từ 80–350 USD (chính xác bằng 2× doanh thu thực của những ngày đó).
2. `detect_distribution_shift` trả về `score = 2.07` (mean_ratio) → `is_anomaly = True`.
3. Query thủ công trên `stg_customers WHERE customer_id='C0042' AND is_active=true` trả về 2 dòng — xác nhận nguồn gốc fan-out.

## Phạm Vi Ảnh Hưởng (Blast Radius)

```text
raw customers table
  └─► stg_customers          (filter is_active=true giữ lại cả 2 dòng)
        └─► fct_daily_revenue (LEFT JOIN nhân bản dòng đơn hàng)
              └─► Dashboard CEO — KPI daily_revenue  ← P1, người dùng thấy trực tiếp
              └─► Các báo cáo/model khác join vào fct_daily_revenue
```

## Biện Pháp Xử Lý

**Sửa ngay lập tức:** Cập nhật `fct_daily_revenue.sql` để loại bỏ trùng lặp khách hàng trước khi JOIN bằng `ROW_NUMBER()`:

```sql
active_customers as (
    select *, row_number() over (
        partition by customer_id order by valid_from desc nulls last
    ) as rn
    from {{ ref('stg_customers') }}
    where is_active = true
),
deduplicated_customers as (select * from active_customers where rn = 1)
```

**Sửa song song:** Vá lỗi bảng chiều upstream — set `is_active = false` cho các dòng cũ mà job SCD không đóng đúng.

## Phục Hồi

1. Chạy `dbt build` với model đã vá → tất cả 21 test đều PASS.
2. `assert_daily_revenue_matches_orders` trả về 0 dòng → mart khớp với dữ liệu gốc.
3. `assert_single_active_customer` trả về 0 dòng sau khi sửa bảng chiều upstream.
4. Dashboard CEO được refresh lại với số liệu doanh thu chính xác.

## Kiểm Tra Xác Nhận

- [x] Contract healthy — `validate_orders` pass toàn bộ kiểm tra cột
- [x] dbt tests healthy — tất cả generic test + singular test đều pass sau khi vá
- [x] Anomaly trở về vùng bình thường — distribution score < 1.1
- [x] SLO healthy / error budget được hiểu rõ — bad_rate về dưới ngưỡng target
- [x] Output downstream đã được xác minh — dashboard CEO hiển thị đúng

## Phòng Ngừa / Hành Động Tiếp Theo

| Hành Động | Người Thực Hiện | Deadline | Lý Do |
|---|---|---|---|
| Thêm `assert_single_active_customer` vào CI blocking gate | Data Engineering | Sprint +1 | Bắt lỗi SCD fan-out trước khi lên prod |
| Thêm `assert_daily_revenue_matches_orders` vào monitor hàng đêm | Data Engineering | Sprint +1 | Đối chiếu doanh thu làm lưới an toàn |
| Sửa job SCD để `UPDATE is_active=false` đúng cho dòng cũ | Data Engineering | Sprint +1 | Sửa nguyên nhân gốc, không chỉ triệu chứng |
| Thêm dbt unit test cho kịch bản fan-out vào PR checks | Data Engineering | Sprint +1 | Shift-left: phát hiện ở PR, không phải prod |
| Thêm alert anomaly trên `daily_revenue` vào PagerDuty | Platform | Sprint +2 | Cảnh báo nếu reconciliation test bị bỏ lỡ |
