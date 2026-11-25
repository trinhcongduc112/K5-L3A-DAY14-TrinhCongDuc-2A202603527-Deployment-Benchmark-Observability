# Deployment — Part 6

## Trạng thái

**Nền tảng** — Render, Blueprint `day14-lab`, branch `main`, commit triển khai `d2f4c39`.

**URL public** — [production-agent-hlw1.onrender.com](https://production-agent-hlw1.onrender.com/health). Render báo web service đã deploy và Key Value khả dụng. Agent và Redis cũng đã được kiểm tra trên Docker Compose local.

| Kiểm tra | Local | Public |
|---|---:|---|
| `GET /health` | `200` | `200` |
| `GET /ready` | `200` | `200` |
| `POST /ask` thiếu `X-API-Key` | `401` | `401` |
| `POST /ask` có `X-API-Key` hợp lệ | `200` | `200` |

## Ảnh triển khai

- [Dashboard Render với web service và Key Value](screenshots/dashboard.png)
- [Web service Live trên Render](screenshots/running.png)
- [Kết quả kiểm tra cả bốn mã HTTP](screenshots/test.png)

## Cấu hình nền tảng

**Render.** Chọn Blueprint Path `06-lab-complete/render.yaml`. Blueprint khai báo web service Docker và Key Value trên gói free. Build context là `06-lab-complete/`. Redis nhận kết nối qua mạng riêng và URL được lấy từ `connectionString`. `AGENT_API_KEY` do Render sinh. [Render Blueprint](https://render.com/docs/infrastructure-as-code) · [Thông số Blueprint](https://render.com/docs/blueprint-spec)

**Railway.** Đặt Root Directory `/06-lab-complete` và Config File Path `/06-lab-complete/railway.toml`. Agent dùng Dockerfile ở root directory và health check `/health`. Tạo Redis trong cùng project rồi đặt `REDIS_URL` tham chiếu tới `REDIS_URL` của Redis, ví dụ `${{Redis.REDIS_URL}}` khi tên service là `Redis`. Đặt `AGENT_API_KEY` trong Variables và tạo public domain cho service agent. [Railway Monorepo](https://docs.railway.com/deployments/monorepo) · [Railway Redis](https://docs.railway.com/databases/redis)

| Biến | Giá trị cấu hình |
|---|---|
| `PORT` | Nền tảng cấp, app mặc định `8000` |
| `AGENT_API_KEY` | Secret đọc từ biến môi trường |
| `REDIS_URL` | URL Redis nội bộ của cùng môi trường deploy |
| `ENVIRONMENT` | `production` |
| `LOG_LEVEL` | `INFO` |
| `RATE_LIMIT_PER_MINUTE` | `10` |
| `MONTHLY_BUDGET_USD` | `10` |
| `DAILY_BUDGET_USD` | `0` mặc định, có thể bật trần ngày bằng số dương |

## Kiểm tra public URL

Đặt `BASE` là URL HTTPS của service. Nạp `AGENT_API_KEY` từ nền tảng vào biến shell, rồi chạy các lệnh dưới đây. Output chỉ gồm mã HTTP.

```bash
curl -sS -o /dev/null -w 'GET /health → %{http_code}\n' "$BASE/health"
curl -sS -o /dev/null -w 'GET /ready → %{http_code}\n' "$BASE/ready"
curl -sS -o /dev/null -w 'POST /ask (thiếu key) → %{http_code}\n' \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}' "$BASE/ask"
curl -sS -o /dev/null -w 'POST /ask (key đúng) → %{http_code}\n' \
  -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}' "$BASE/ask"
```
