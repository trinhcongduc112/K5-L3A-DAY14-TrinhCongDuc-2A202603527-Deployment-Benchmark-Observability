# Benchmark & Observability Report — Day 14

- **Họ tên:** Trinh Cong Duc
- **MSSV:** 2A202603527
- **Ngày chạy:** 25/11/2026 (GMT+7)
- **Môi trường:** Linux amd64, Python 3.12 local, Docker 29.8.1, Locust 2.47.0. Stack dùng Python 3.11, giới hạn mỗi replica 0,5 CPU và 256 MB RAM.

## 1. SLO của agent

| SLI | Ngưỡng | Lý do |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Giới hạn độ trễ mà ít nhất 95% request phải đạt, kể cả khi một nhóm nhỏ bị chậm. |
| Error rate `/ask` | < 2% | Trần lỗi cho bài load test. Mock có xác suất lỗi mặc định 1%. |
| Accuracy trên golden dataset | ≥ 80% | Ngưỡng mặc định của eval. Lượt xác minh bản sửa dùng ngưỡng 100% và so baseline. |

Quy tắc alert của stack dùng ngưỡng vận hành 5% lỗi trong 1 phút và p95 trên 1 giây trong 2 phút. Ngưỡng cao hơn và điều kiện duy trì tránh cảnh báo khi chỉ có một đợt tăng ngắn.

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency và latency của v2

Mỗi lượt gồm 300 request. Các file thực đo nằm trong [`reports/`](reports/).

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 4,66 | 190,1 | 219,2 | 1682,3 | 0,67% | PASS |
| 10 | 40,83 | 193,7 | 220,3 | 1689,4 | 1,67% | PASS |
| 50 | 132,38 | 194,0 | 236,8 | 1694,4 | 0,67% | PASS |
| 100 | 77,49 | 294,2 | 2353,4 | 2552,0 | 1,00% | FAIL do p95 |

RPS tăng đến concurrency 50 rồi giảm khi lên 100. Cùng lúc đó cả p50 và tail latency tăng. Tải đồng thời cao hơn có thể làm tăng thời gian chờ ở đường xử lý request; phép đo này chưa phân tách thời gian chờ giữa client, server và mock LLM. Mức 50 có throughput cao nhất trong bốn lượt và vẫn đạt cả hai ngưỡng SLO.

### 2.2 Tail latency

Mỗi lượt gồm 300 request với concurrency 20. Server được khởi động lại khi đổi `MOCK_SLOW_RATE`.

| `MOCK_SLOW_RATE` | Avg (ms) | p95 (ms) | p99 (ms) |
|---:|---:|---:|---:|
| 0 | 190,7 | 220,4 | 225,4 |
| 0,03 | 268,9 | 599,3 | 1706,2 |
| 0,1 | 287,2 | 1684,6 | 1722,0 |

Từ 0 lên 0,03, trung bình tăng 78,2 ms còn p99 tăng 1480,8 ms. Ở 0,1, nhóm request chậm đủ lớn để ảnh hưởng cả p95. Theo dõi p95 cho SLO và p99 để phát hiện sớm tail latency.

### 2.3 Metrics của bản develop

`/metrics` công bố `http_requests_total` là Counter, `agent_in_flight_requests` là Gauge và `agent_question_length_chars` là Histogram. Sau lượt eval 23 câu, `agent_question_length_chars_count` bằng `23`. Label `route` theo mẫu route gộp mọi URL không khớp vào `unmatched`. Mỗi URL thật làm một label riêng sẽ tạo thêm time series khi có nhiều đường dẫn ngẫu nhiên và làm tăng RAM của Prometheus.

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 sau khi sửa KB |
|---|---:|---:|---:|
| Accuracy | 4,35% (1/23) | 91,30% (21/23) | 100% (23/23) |
| Avg tokens / câu | 57,8 | 109,1 | 113,7 |
| Tổng chi phí (USD) | 0,000414 | 0,000762 | 0,000791 |
| Chi phí / câu đúng (USD) | 0,00041415 | 0,00003627 | 0,00003438 |
| p50 latency (ms) | 162,2 | 186,7 | 198,4 |
| p95 latency (ms) | 189,7 | 1549,0 | 222,5 |
| Quality gate | FAIL | PASS | PASS |

| Câu v2 bỏ sót | Keyword thiếu | Sửa knowledge base |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm mô tả JWT có chữ ký và thời hạn, phân biệt với API key cố định. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm tài liệu HPA với CPU, memory và custom metrics như RPS và độ dài hàng đợi. |

Retrieval làm prompt dài hơn và tăng median latency. v2 sau sửa có chi phí trên mỗi câu đúng thấp hơn khoảng 12 lần so với v1. p95 của eval biến động do chỉ có 23 câu và mock có độ trễ ngẫu nhiên. `eval_v2_fixed.json` xác nhận 23/23 và 0 regression khi dùng `eval_v2.json` làm baseline. Lượt kiểm tra lại với fault injection tắt cũng đạt 23/23 và 0 regression.

**Quality gate trong CI.** Trên mỗi pull request, khởi động agent v2 với `MOCK_ERROR_RATE=0`, chờ `/health` trả 200, rồi chạy `python eval/run_eval.py --url http://127.0.0.1:8000 --min-accuracy 0.85 --baseline reports/eval_v2_fixed.json`. Script thoát mã `1` nếu accuracy dưới 85% hoặc có câu regression. Đặt job eval làm required status check để chặn merge khi job fail.

## 4. Observability stack (production)

### 4.1 Dashboard và bằng chứng

- [Grafana khi chạy tải với ba replica](screenshots/grafana-dashboard.png)
- [Jaeger, trace chậm](screenshots/jaeger-slow-trace.png)
- [Jaeger, trace lỗi có event `exception`](screenshots/jaeger-error-trace.png)
- [Prometheus, các alert cùng `firing`](screenshots/prometheus-alert-firing.png)

Lúc chụp, Grafana hiển thị `54,3 req/s`, error rate `0,81%`, p95 `295,56 ms`, saturation `13` request đang xử lý và 3 instance. Truy vấn cùng bộ biểu thức PromQL tại mốc `22:38:04` trả avg `238,39 ms` và p95 `296,00 ms`. Khoảng cách gần 58 ms cho thấy phần đuôi của phân bố. p99 ở mốc đó là `1836,24 ms`.

Tốc độ từng instance là `19,35`, `18,77` và `18,92 req/s`, tương đối đều. Input `4318,71 token/s` cao hơn output `2226,94 token/s` vì v2 thêm context retrieval vào prompt. Panel Tokens/s xếp chồng hai series, nên mép trên là tổng input và output. Gọi `/metrics` qua Nginx trả `404` vì endpoint chỉ dành cho Prometheus scrape trực tiếp qua mạng nội bộ.

### 4.2 Chaos và alert

A và B được bật cùng một lần tạo lại agent. Locust dùng 30 users, ramp 5 users/s. Thời gian tính từ lệnh đổi cấu hình tới lần đầu API Prometheus báo `firing`. Alert rules gốc chạy qua `promtool test rules` thành công.

| Ca | Thay đổi | Kết quả | Tới `firing` | Panel theo dõi |
|---|---|---|---:|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` firing, tỷ lệ 5xx đạt 21,3% lúc phát hiện | 102,0 s | Error rate, Requests/s theo status code |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` firing, p95 đạt 1,89 s lúc phát hiện | 147,2 s | Latency p95, Latency /ask |
| C | `LLM_MODEL=mock-llm-large` | Chưa đo riêng. `LLMCostBurnRateHigh` đã firing ở lượt 100 users với model small, trước khi bật A và B. | — | Cost burn rate (USD/giờ) |
| D | `docker pause` một replica | `AgentInstanceDown` firing, `up=0` cho replica bị pause | 39,2 s | Instances up và Prometheus Targets |
| E | `AGENT_VERSION=v1` | Đã đo chất lượng local 1/23. Alert rules của stack không có điều kiện về accuracy. | — | Phiên bản đang chạy và eval ngoài stack |

Prometheus đánh giá rule mỗi 5 giây. A và B cần vượt ngưỡng liên tục lần lượt trong 1 phút và 2 phút. Thời gian đo còn bao gồm khởi động container, DNS discovery, scrape và cửa sổ `rate()`.

Với D, container bị pause vẫn có tên trong Docker DNS, nên scrape thất bại và tạo `up=0`. Nếu Nginx trả `504` do hết thời gian đợi, agent chưa hoàn thành request để ghi vào counter của nó. Giám sát thêm HTTP status tại Nginx hoặc dùng probe qua gateway để thấy lỗi người dùng nhận được.

Với E, dùng golden dataset trong CI và chạy synthetic eval định kỳ sau deploy. Có thể theo dõi accuracy theo `agent_version` và đặt alert khi chất lượng xuống dưới ngưỡng hoặc phiên bản đang chạy không đúng.

### 4.3 Debug bằng trace

**Trace chậm** `e6c95ff26c86b6439c250a977577bf02`. `POST /ask` mất `1721,22 ms`. Bên trong `agent.run`, bước `chat mock-llm-small` mất `1697,11 ms`, chiếm `98,6%` tổng thời gian. Bước `agent.retrieve_context` mất `18,85 ms`.

```json
{"ts":"2026-11-25T15:35:10.381668+00:00","level":"INFO","service":"observable-agent","instance":"51a7ba98cfb4","event":"llm_call","trace_id":"e6c95ff26c86b6439c250a977577bf02","span_id":"b4adfc609b6e7d0b","request_id":"9caa9ab2dd7e","model":"mock-llm-small","agent_version":"v2","input_tokens":83,"output_tokens":44,"cost_usd":3.9e-05,"llm_ms":1695.9}
```

**Trace lỗi** `a2ef8fa6fa742dc19c60b87e671aaf94`. `POST /ask` trả `503` sau `97,95 ms`. Jaeger ghi event `exception` trên span `chat mock-llm-small` và span cha `agent.run`. `trace_id` trong dòng `llm_error` khớp trace.

```json
{"ts":"2026-11-25T15:34:13.937327+00:00","level":"INFO","service":"observable-agent","instance":"51a7ba98cfb4","event":"llm_error","trace_id":"a2ef8fa6fa742dc19c60b87e671aaf94","span_id":"ecce908423e4d857","request_id":"7efdf42d5f51","error":"Upstream LLM error: 503 Service Unavailable (mock)"}
```

## 5. Benchmark scaling (production, Locust headless)

Mỗi lần dùng 100 users, ramp-up 10 users/s trong lượt chạy 2 phút. Số liệu trong bảng lấy từ dòng `POST /ask`. Agent v2 dùng `mock-llm-small`, `MOCK_ERROR_RATE=0.01` và `MOCK_SLOW_RATE=0.03`. Locust đi qua cùng Nginx trong cả hai lượt. Cổng Nginx trên máy là `18080` vì `8080` đã có ứng dụng sử dụng. `--no-deps` giữ nguyên số replica của lượt đo.

| Replica | Requests | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---:|---:|---:|---:|---:|---:|---:|
| [1](benchmark-results/scale_1_stats.csv) | 7035 | 59,01 | 200 | 530 | 1700 | 69 (0,98%) |
| [3](benchmark-results/scale_3_stats.csv) | 7122 | 59,75 | 200 | 270 | 1700 | 66 (0,93%) |

Scale lên ba replica giảm p95 khoảng 49% trong phép đo này. RPS chỉ tăng 1,3% do workload có số user cố định và thời gian nghỉ 0,5–2 giây giữa lượt gọi. p99 giữ ở khoảng 1,7 giây, phù hợp với nhánh phản hồi chậm của mock LLM. Phép đo cho thấy cải thiện ở p95 trong cấu hình thử, chưa xác định throughput tối đa của mỗi cấu hình.

## 6. Kết luận

1. Phải lưu cả throughput, error rate và percentile. p99 phát hiện nhóm request chậm khi median vẫn ổn.
2. Accuracy, số token và chi phí trên mỗi câu đúng giải thích được lợi ích và chi phí của retrieval.
3. Metrics phát hiện triệu chứng theo thời gian. Trace chỉ ra span chậm và `trace_id` nối sự kiện đó với log ứng dụng.

Khi vận hành thật, bổ sung tỷ lệ `5xx` và timeout ở gateway, synthetic probe đo p95 của người dùng, và một phép eval định kỳ để theo dõi accuracy theo phiên bản.
