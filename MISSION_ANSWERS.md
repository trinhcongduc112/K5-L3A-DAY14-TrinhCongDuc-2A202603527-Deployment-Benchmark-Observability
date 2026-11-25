# Day 14 — Mission Answers

## Part 1 — Localhost vs Production

### Exercise 1.1 — Anti-patterns

1. [Dòng 15–18](01-localhost-vs-production/develop/app.py#L15) đặt API key và mật khẩu giả trực tiếp trong mã mẫu. Với credential thật, người có quyền đọc repo hoặc image có thể lấy được.
2. [Dòng 20–22](01-localhost-vs-production/develop/app.py#L20) cố định cấu hình trong mã, nên đổi môi trường phải sửa source.
3. [Dòng 32–38](01-localhost-vs-production/develop/app.py#L32) dùng `print()` và ghi cả giá trị key vào log.
4. [Dòng 42–43](01-localhost-vs-production/develop/app.py#L42) chỉ ra app thiếu liveness probe để bộ điều phối phát hiện tình trạng process.
5. [Dòng 49–53](01-localhost-vs-production/develop/app.py#L49) bind `localhost`, cố định cổng `8000` và bật auto-reload. Môi trường container cần lắng nghe qua giao diện mạng của container và đọc cổng được cấp.
6. Bản develop thiếu `lifespan` để quản lý khởi tạo và đóng tài nguyên. [Bản production bổ sung `lifespan`](01-localhost-vs-production/production/app.py#L39) và chỉ báo ready sau khi khởi tạo.

### Exercises 1.2–1.3 — Chạy hai phiên bản

Bản develop nhận `question` từ query. Trích kết quả `curl -i -X POST 'http://127.0.0.1:18083/ask?question=Hello'`:

```http
HTTP/1.1 200 OK
content-type: application/json

{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

Bản production nhận body JSON `{"question":"What is Docker?"}`, trả `200` và câu trả lời chứa `Build once, run anywhere!`. `/health` trả `status: ok` và `/ready` trả `ready: true`.

| Hạng mục | Develop | Production | Ý nghĩa |
|---|---|---|---|
| Cấu hình | Hằng số trong source | `Settings` đọc biến môi trường, gồm `HOST`, `PORT` và `DEBUG` | Một bản build có thể dùng ở nhiều môi trường |
| Health check | Có trang `/` | `/health` cho liveness, `/ready` cho readiness | Bộ điều phối biết process còn sống và khi nào có thể gửi lưu lượng |
| Logging | `print()`, ghi cả key | Logging có trường và sự kiện, bỏ giá trị key khỏi log request | Dễ tìm sự kiện và hạn chế lộ thông tin nhạy cảm |
| Shutdown | Thiếu bước quản lý vòng đời của ứng dụng | Uvicorn xử lý tín hiệu khi chạy `python app.py`, `lifespan` chạy bước cleanup | Request đang xử lý có thời gian hoàn thành và tài nguyên được đóng |

## Part 2 — Docker

### Exercise 2.1 — Dockerfile

1. Base image của develop là `python:3.11`, cung cấp Python và các thành phần hệ thống cần để chạy app.
2. `WORKDIR /app` đặt thư mục làm việc cho các lệnh sau và làm điểm xuất phát cho các đường dẫn tương đối.
3. Docker copy `requirements.txt` và cài dependencies trước khi copy source để có thể tái sử dụng layer cài đặt khi chỉ sửa source.
4. `ENTRYPOINT` định nghĩa chương trình chạy chính. `CMD` cung cấp lệnh mặc định hoặc tham số mặc định cho `ENTRYPOINT`, và đối số truyền sau tên image sẽ ghi đè `CMD`.

### Exercises 2.2–2.3 — Build, chạy và đo image

`POST /ask?question=What%20is%20Docker%3F` qua container develop ở cổng `18082` trả `HTTP/1.1 200 OK` và câu trả lời mock về Docker. Kích thước đo bằng `docker image inspect --format '{{.Size}}'`, quy đổi theo `1 MB = 1.000.000 byte`.

| Image | Số byte | Dung lượng |
|---|---:|---:|
| `my-agent:develop` | 1.667.784.131 | 1.667,78 MB |
| `my-agent:advanced` | 239.815.486 | 239,82 MB |

Image advanced nhỏ hơn **85,62%**. Builder dùng `python:3.11-slim`, cài `gcc` và `libpq-dev` để build dependency rồi cài Python package vào `/root/.local`. Runtime dùng base slim và copy package đã cài cùng source, chạy dưới `appuser`. Build tools nằm ở builder.

### Exercise 2.4 — Docker Compose

```text
Client → Nginx :80 → agent :8000 (2 replicas)
                     ├── Redis :6379 (cache / session)
                     └── Qdrant :6333 (vector store)
```

Compose đặt các service trên mạng `internal`. Agent nhận địa chỉ Redis và Qdrant qua biến môi trường. Compose đợi cả hai có trạng thái healthy trước khi khởi động agent. Nginx công bố cổng ngoài và chuyển request tới agent; ví dụ `/ask` gọi mock LLM.

```text
GET  http://127.0.0.1/health  → 200 OK, Server: nginx, status: ok
POST http://127.0.0.1/ask     → 200 OK, Server: nginx, answer có nội dung
```

## Part 3 — Cloud Deployment

Agent `06-lab-complete/` đã deploy lên Render từ Blueprint `day14-lab`. URL public là `https://production-agent-hlw1.onrender.com`. Kiểm tra public xác nhận `/health` và `/ready` trả `200`. `POST /ask` thiếu key trả `401` và có key hợp lệ trả `200`. Các ca kiểm tra và cấu hình được ghi trong [DEPLOYMENT.md](DEPLOYMENT.md).

### Exercises 3.1–3.2 — Railway và Render

| Hạng mục | Railway | Render |
|---|---|---|
| Cách khai báo | `railway.toml` đặt `DOCKERFILE`, `/health` và restart policy `ON_FAILURE` | `render.yaml` mô tả web service Docker, đường dẫn build context, `/health` và một Key Value service |
| Redis | Tạo Redis trong cùng project, tham chiếu `REDIS_URL` của Redis từ app | Blueprint lấy URL nội bộ bằng `fromService` và `connectionString` |
| API key | Đặt `AGENT_API_KEY` trong Variables của service | Blueprint sinh giá trị cho `AGENT_API_KEY` bằng `generateValue` |
| Domain | Bật Public Networking và tạo domain cho service | Web service được cấp hostname `onrender.com` |

### Exercise 3.3 — Cloud Run

1. `cloudbuild.yaml` định nghĩa bước cài dependency rồi chạy `pytest`.
2. Bước Docker build tạo image với hai tag `$COMMIT_SHA` và `latest`, sau đó push chúng lên registry.
3. `gcloud run deploy` lấy image theo commit SHA, triển khai `ai-agent` ở `asia-southeast1` và tham chiếu secret từ Secret Manager.
4. `service.yaml` cung cấp cấu hình triển khai khai báo với 1–10 instance, concurrency 80, timeout 60 giây, port 8000, liveness `/health` và startup probe `/ready`.

## Part 4 — API Security

### Exercises 4.1–4.3 — API key, JWT và rate limit

`verify_api_key` là dependency của `/ask` trong bản develop. Nó đọc `X-API-Key`, trả 401 khi thiếu và 403 khi sai. Để rotate, cập nhật `AGENT_API_KEY` trên môi trường triển khai, nạp cấu hình mới và chuyển client sang key mới.

Trích output `curl -i` của bản develop:

```http
HTTP/1.1 401 Unauthorized
content-type: application/json

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```

```http
HTTP/1.1 403 Forbidden
content-type: application/json

{"detail":"Invalid API key."}
```

```http
HTTP/1.1 200 OK
content-type: application/json

{"question":"What is Docker?","answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

`POST /auth/token` xác thực tài khoản demo, ký JWT HS256 với `sub`, `role`, `iat` và `exp`, rồi trả bearer token có hiệu lực 60 phút. `/ask` kiểm tra chữ ký và thời gian hết hạn trước khi dùng `sub` và `role` để chọn quota. Token đã được che khỏi kết quả.

```http
HTTP/1.1 200 OK
content-type: application/json

{"question":"What is Docker?","answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!","usage":{"requests_remaining":9,"budget_remaining_usd":1.9e-05}}
```

Bản mẫu lưu timestamp trong `deque` cho từng user. Sliding window loại timestamp cũ hơn 60 giây rồi kiểm tra số request còn trong cửa sổ. Role user có 10 request/phút, role admin có 100 request/phút qua limiter riêng. Sau một lần gọi hợp lệ, vòng lặp 20 request bằng cùng JWT có 9 lần `200`, rồi 11 lần `429`.

```http
HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
retry-after: 59
content-type: application/json

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

### Exercise 4.4 — Cost guard

Với quota 10 USD/tháng cho từng user, lấy định danh từ JWT đã xác thực và lưu chi phí vào Redis theo key `budget:<user_id>:<tháng UTC>`. Kiểm tra `đã dùng + chi phí dự kiến` và cập nhật trong cùng thao tác nguyên tử. Trả `402` khi vượt ngưỡng. Đổi key khi sang tháng và đặt TTL dọn key cũ. Rate limit giới hạn tần suất, cost guard giới hạn tổng chi tiêu kể cả khi lưu lượng dưới quota request.

Part 6 dùng một API key của service nên áp ngân sách tổng mặc định 10 USD/tháng, có thể bật thêm trần ngày qua env. Nó kiểm tra số dư trước khi gọi mock, tính chi phí từ token rồi kiểm tra và ghi chi phí bằng một script Redis nguyên tử. Bộ chấm trả `402` khi ngân sách thử thấp hơn chi phí của request đầu tiên.

## Part 5 — Scaling & Reliability

- **5.1 Health và readiness.** `GET /health` là liveness của process, `GET /ready` cho biết instance nhận traffic được hay chưa. Hai endpoint trả `200` khi bản demo đã khởi động. Trong Part 6, mất Redis làm `/ready` trả `503` trong khi `/health` vẫn trả `200`.
- **5.2 Graceful shutdown.** Chạy bản develop bằng `python app.py`, gửi `POST /ask`, rồi gửi `SIGTERM` khi request đang chạy. Request trả `200`, log ghi `Graceful shutdown initiated` và `Shutdown complete`, process thoát mã `0`.
- **5.3 Stateless.** Session đặt theo `session_id` trong Redis. Tất cả replica đọc được lịch sử nên Nginx có thể phân tải mà không cần sticky session. Khi lưu trong RAM, mỗi replica chỉ thấy phần lịch sử do chính nó xử lý.
- **5.4 Load balancing.** Ba replica chạy sau Nginx. Dùng cổng local `18081` vì cổng `8080` đã được ứng dụng khác sử dụng. Header/body phản hồi của `/chat` cho biết instance thực sự nhận request.
- **5.5 Test stateless.** `test_stateless.py` chạy với cổng local `18081`. Năm lượt chat được phục vụ bởi `instance-3cfb75`, `instance-83542b`, `instance-d6aa4b`; đọc Redis qua API đủ 10 tin nhắn. Sau khi dừng một replica, gửi tiếp bốn câu trên cùng session. Hai replica còn lại trả đủ bốn câu và endpoint history đếm 18 tin nhắn.

```text
Total requests: 5
Instances used: {'instance-d6aa4b', 'instance-3cfb75', 'instance-83542b'}
✅ All requests served despite different instances!
Total messages: 10
✅ Session history preserved across all instances via Redis!

Sau khi dừng một replica: 4/4 request trả lời thành công, history count = 18.
```

## Part 6 — Production readiness

Chạy script chấm đầy đủ có Docker. Image được bộ chấm đo `273 MB`. `docker stop` hoàn tất trong `0,5 giây` với mã thoát `0`. Kiểm tra bổ sung trên Docker Compose xác nhận câu hỏi rỗng trả `422`. Sau một request hợp lệ, đợt 20 request đồng thời có 9 mã `200` và 11 mã `429`, đúng giới hạn 10 request/phút.

```text
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================

```

## AI log

| Yêu cầu | Hỗ trợ của Codex | Cách kiểm chứng |
|---|---|---|
| Đọc repo và hoàn thiện đầu ra theo checklist K5 | Đọc rubric, soạn câu trả lời và ghi các kết quả Part 1–5 | Codex chạy các app mẫu, `curl -i`, Docker Compose, đo kích thước image và kiểm tra ba replica cùng Redis |
| Rà soát Part 6 và hoàn thiện cấu hình deploy | Codex cập nhật xác thực, quota Redis nguyên tử, xử lý Redis mất kết nối, shutdown và cấu hình Render | Codex chạy bộ chấm gốc với Docker, thử input lỗi, xác thực và burst trên stack local |
| Hoàn thiện benchmark và observability | Codex thêm histogram độ dài câu hỏi, sửa môi trường Python của image observability, chạy lại quality gate, đo Locust và chụp dashboard, trace, alert | Kết quả đối chiếu với JSON, CSV, API Prometheus, Jaeger và log của container. Kiểm thử của người nộp chưa được ghi nhận trong phiên này |
