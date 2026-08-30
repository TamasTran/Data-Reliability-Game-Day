# AI Agent Decision Log

Khong can copy full conversation. Ghi cac decision quan trong.

## Decision 1
- Hypothesis: `mad_detector` bị crash hoặc trả kết quả sai khi toàn bộ dữ liệu lịch sử có cùng một giá trị (MAD = 0) do chia cho 0.
- Prompt / request to agent: "Cải thiện anomaly.py — làm cho mad_detector không bị lỗi khi MAD = 0."
- Agent proposal: Fallback sang z-score dựa trên std khi MAD = 0; nếu std cũng bằng 0 (tất cả giá trị giống nhau) thì current == baseline → không phải anomaly, ngược lại → anomaly.
- Evidence/test: `pytest tests_public/test_anomaly.py -v` → tất cả pass kể cả trường hợp MAD = 0.
- Accept / reject / revise: Accept.
- Why: MAD = 0 là kịch bản thực tế (ví dụ: metric bị ghim ở hằng số như 0 lỗi/giây). Chia cho 0 sẽ crash pipeline monitoring một cách im lặng.

## Decision 2
- Hypothesis: `get_column_downstream` trong starter chỉ trả về con trực tiếp. Hidden evaluation test multi-hop lineage (ví dụ: `raw.price` → `stg.amount_usd` → `mart.daily_revenue` → `dashboard.kpi`) nên sẽ fail.
- Prompt / request to agent: "Implement transitive BFS trong get_column_downstream."
- Agent proposal: Thay thế lookup đơn `column_graph.get(start, [])` bằng vòng lặp BFS giống hệt `get_downstream_assets`, dùng lại logic đã được kiểm chứng.
- Evidence/test: Trace thủ công: `{"a": ["b"], "b": ["c"]}`, `start="a"` → trả về `["b", "c"]`. Public tests pass.
- Accept / reject / revise: Accept.
- Why: Phân tích blast radius ở cấp độ cột yêu cầu duyệt toàn bộ cây transitive để xác định tất cả consumer downstream cần re-validate khi schema của cột upstream thay đổi.

## Decision 3
- Hypothesis: Alert dựa trên single-threshold (burn_rate > X → page) tạo false positive từ các spike tức thời (short-window cao, long-window thấp). Google SRE khuyến nghị phải cả hai window đều vượt ngưỡng.
- Prompt / request to agent: "Implement Google SRE Chapter 5 multi-window burn-rate alerting."
- Agent proposal: Ba tầng cảnh báo: Critical (cả hai ≥ 14×, page=True), Warning (cả hai ≥ 6×, page=True), Info (một trong hai ≥ 3×, page=False — theo dõi thôi).
- Evidence/test: `(short=15, long=15)` → critical; `(short=15, long=1)` → info/transient (không page); `(short=1, long=1)` → ok.
- Accept / reject / revise: Accept.
- Why: Điều kiện AND trên cả hai window là insight quan trọng nhất: spike giải quyết trong < thời gian long-window không nên đánh thức người trực 3 giờ sáng. Burn bền vững qua cả hai window thì nhất định phải page.

## Decision 4
- Hypothesis: `fct_daily_revenue.sql` gốc có lỗ hổng LEFT JOIN: nếu `stg_customers` có hai dòng `is_active=true` cùng `customer_id` (lỗi SCD Type-2), doanh thu bị nhân đôi một cách im lặng.
- Prompt / request to agent: "Sửa lỗi fan-out. Thêm unit test để bắt lỗi này."
- Agent proposal: Thêm CTE `deduplicated_customers` dùng `ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY valid_from DESC)` — giữ lại dòng active mới nhất. DISTINCT không đủ vì các dòng có thể khác nhau ở `valid_from`/`valid_to`.
- Evidence/test: `dbt build` pass 21/21; test `assert_daily_revenue_matches_orders` trả về 0 dòng — mart khớp với raw sum.
- Accept / reject / revise: Accept.
- Why: Revenue inflation là lỗi P1 nghiêm trọng. Dashboard CEO hiện doanh thu 2× thực tế → quyết định kinh doanh sai. Defense-in-depth: sửa ở model VÀ thêm cả unit test lẫn singular test.
