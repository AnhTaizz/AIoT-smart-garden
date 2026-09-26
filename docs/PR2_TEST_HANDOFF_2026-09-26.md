# Bản ghi kiểm thử và bàn giao PR #2 — 2026-09-26

## Phiên bản và phạm vi

- Repository: `https://github.com/AnhTaizz/AIoT-smart-garden.git`.
- PR: [#2 — G02 Safe command contract, backend and simulator](https://github.com/AnhTaizz/AIoT-smart-garden/pull/2), trạng thái draft tại thời điểm kiểm tra; base `main`, head `feat/B-W1-backend-telemetry-command`.
- `origin/main`: `adbdbd1b3c1b2829661cf53d603392750b6a39f3`.
- Code được kiểm tra: `6ba6eb46ca7a06f6f9a258a8900e5edfb1384577`; local HEAD khớp remote head sau `git fetch origin --prune`.
- Khi bắt đầu phiên, working tree sạch và không có thay đổi chỉ tồn tại local. Bản ghi/tài liệu bàn giao này được thêm sau khi code trên SHA trên đã PASS; không sửa code hoặc schema database trong lượt kiểm tra.

`main` đã có khung Compose, health/readiness và dashboard cơ bản. Subscriber, migration nghiệp vụ, telemetry storage, latest/history REST, command/ACK/state và simulator hai chiều chỉ có trên PR #2, chưa merge. UI telemetry/command, smartphone LAN, ESP32/relay/bơm thật, firmware và AI chưa được triển khai hoặc chưa được kiểm chứng.

## Mục tiêu và quyết định

Phiên này kiểm tra lại ba lỗi đã yêu cầu sửa, cập nhật trạng thái thật và bàn giao dependency cho Toản làm C-W1. Không mở rộng chức năng:

1. Mất MQTT khi simulator đang bơm phải tắt relay, hủy timer; reconnect không bật lại; ON trùng không chạy lại.
2. Bằng chứng thứ hai được xử lý tại/sau `expires_at` phải làm command `timeout` ngay trong transaction, kể cả sweeper chưa chạy; vẫn giữ bằng chứng và cập nhật current state hợp lệ.
3. ACK `accepted` đến sau ACK `applied` không được làm lùi `device_ack` hoặc giữ command ở `pending`.

G02 tiếp tục là **DRAFT**. Kết quả dưới đây là bằng chứng triển khai/kiểm thử thành phần, không phải xác nhận của Thành/Tài/Toản và không làm M1 PASS.

## Môi trường

| Thành phần | Giá trị dùng trong phiên |
| --- | --- |
| Hệ điều hành | Microsoft Windows NT `10.0.26200.0` |
| PowerShell | `5.1.26100.9444` |
| Git | `2.49.0.windows.1` |
| Docker client/server | `29.4.3` / `29.4.3` |
| Docker Compose | `v5.1.3` |
| Backend test container | Python `3.12.14`, pytest `8.4.1` |
| Simulator unit trên host | Python `3.9.13` |
| Dịch vụ tích hợp | PostgreSQL `16-alpine`, Eclipse Mosquitto `2.0`, backend FastAPI và frontend/Nginx từ `compose.yaml` |
| Cấu hình cổng local | Development bind; PostgreSQL host port `55432`, cổng nội bộ vẫn `5432` |

Không in hoặc lưu password từ `.env`. Hai cấu hình Compose được kiểm tra bằng chế độ quiet để không đưa giá trị môi trường vào log.

## Lệnh và kết quả thực tế

| Kiểm tra | Lệnh/thao tác | Kết quả 2026-09-26 |
| --- | --- | --- |
| Compose development | `docker compose config --quiet` | PASS |
| Compose LAN override | `docker compose -f compose.yaml -f compose.lan.yaml config --quiet` | PASS |
| Build/start stack | `docker compose up --build -d`, sau đó `docker compose ps` | PASS; PostgreSQL, Mosquitto, backend và frontend đều `healthy` trong phiên |
| Simulator unit | từ `simulator/`: `python -m unittest discover -s tests -v` | **31 passed**, không skip, 1.848 giây |
| Backend validation | container Python 3.12, `python -m pytest -v tests/test_validation.py` | **51 passed**, không skip, 1.45 giây |
| Backend E2E thật | container test trên mạng `smart-garden_default`, `python -m pytest -v tests/e2e` | **33 passed**, không skip, 102.28 giây |
| Broker disconnect | simulator thật → API ON → dừng Mosquitto → khởi động lại → phát lại payload ON cũ | PASS; chi tiết bên dưới |

Không có test bị skip. Frontend test/build không chạy lại riêng trong phiên này vì không sửa frontend; bước build Compose dùng layer frontend đã cache, nên không được ghi như một lần chạy Vitest/build mới. Không có ảnh hoặc video được tạo trong phiên.

## Bằng chứng regression cho ba lỗi

### 1. Mất MQTT khi đang bơm

- Unit `test_disconnect_stops_pump_and_reconnect_does_not_replay_on` xác nhận callback đặt relay `off`, xóa `running_command_id`, đặt `pump_stop_at` về `None`, không publish trên kết nối chết, giữ `order_mark`/bộ nhớ outcome qua reconnect và không chạy lại ON trùng.
- Tích hợp thật dùng device `disconnect_110231`, command `b5af82c2-6bed-43e2-81f5-20c6b4d3530d`:
  - trước disconnect: command `applied`, relay `on`, `state_sequence=2`;
  - dừng rồi khởi động lại Mosquitto: state mới `off`, `state_sequence=5`;
  - publish lại chính payload ON cũ: relay vẫn `off`, state quan sát ở `state_sequence=7`.
- Hai lần orchestration sơ bộ cố đọc `docker logs` bị PowerShell coi output stderr thông thường của Docker là exception; các lần đó đã dọn simulator tạm và bật lại broker, không được tính là kết quả. Kết quả phía trên đến từ lượt hoàn tất quan sát qua API.

### 2. Bằng chứng thứ hai đến sau hạn

E2E PostgreSQL thật chạy các regression xác định, không chờ sweeper:

- `test_state_second_after_deadline_times_out_and_keeps_evidence`: command còn `pending`, test đặt `expires_at = clock_timestamp()` khi giữ transaction rồi đưa state thứ hai vào. Kết quả là `timeout`; ACK `applied`, `confirmed_relay_state=on`, boot và `state_confirmed_at` vẫn được giữ; current device state vẫn cập nhật `on` với đúng command.
- `test_ack_second_after_deadline_times_out_and_keeps_earlier_state`: state đến trước, ACK thứ hai đến tại hạn. Kết quả là `timeout`, `late_ack=applied` và bằng chứng state/boot trước đó vẫn còn.
- `test_both_evidence_before_deadline_applies` vẫn PASS, chứng minh đường hợp lệ trước hạn không bị regression.

### 3. ACK accepted đến sau ACK applied

E2E `test_applied_ack_cannot_be_downgraded_by_repeated_accepted` phát ACK `applied`, sau đó phát lại `accepted`. `device_ack` vẫn là `applied`; khi state phù hợp đến, command chuyển `applied`, không kẹt `pending`. Các ca accepted lặp trước applied, accepted từ boot sai và ACK lặp trên trạng thái final cũng PASS trong bộ 33 E2E.

## Bàn giao cho Toản — C-W1

Dependency bắt buộc là nhánh `feat/B-W1-backend-telemetry-command` của PR #2; không dùng `main` hiện tại vì thiếu API nghiệp vụ. Cách chạy chuẩn nằm trong [backend README](../backend/README.md) và [simulator README](../simulator/README.md). Contract REST/MQTT và response mẫu nằm trong [INTERFACES](INTERFACES.md), vẫn DRAFT để Toản review.

Checklist đầu ra C-W1:

- Hiển thị latest/history telemetry lấy từ `/api`, không dùng số giả.
- Phân biệt `loading`, `empty`, `error`, `stale` và `simulated`.
- Gửi `pump_on` kèm thời lượng và gửi được `pump_off`.
- Poll command theo contract; hiển thị `pending/applied/rejected/timeout`, không suy luận thành công từ HTTP 202.
- Hiển thị current relay state từ `/devices/{id}/state` riêng với kết quả của command.
- STOP vẫn thao tác được khi ON đang `pending` nếu API còn kết nối.
- Cleanup timer/request khi component unmount và dừng poll nhanh khi command đạt trạng thái final.
- Dùng đường dẫn tương đối `/api`; sau kiểm thử desktop phải mở và thao tác trên smartphone cùng LAN bằng IP laptop.

Điều kiện hoàn thành C-W1 không chỉ là UI render: telemetry phải đi qua MQTT/PostgreSQL/API, command phải quay về simulator và UI chỉ báo thành công sau ACK + state. C-W1-02 tiếp tục chịu trách nhiệm responsive và phiên smartphone LAN thật.

## Giới hạn và xác nhận còn thiếu

- G02 chưa được Thành, Tài và Toản xác nhận; PR #2 vẫn draft và chưa merge.
- Chưa chạy UI telemetry/command, frontend test mới, smartphone LAN hoặc phiên M1 end-to-end đầy đủ.
- Chưa kiểm tra ESP32, cảm biến, relay, bơm, dòng nước, đồng bộ giờ ESP32, firmware, camera hoặc AI.
- Broker disconnect integration chứng minh state simulator trở về OFF sau reconnect và ON cũ không bật lại; việc timer nội bộ trở về `None` được chứng minh bằng unit test, không quan sát trực tiếp qua API.
- Không có log/ảnh/video ngoài output lệnh trong phiên; không tạo artifact giả. Dữ liệu simulator luôn là `simulated: true`, không phải số đo cây thật.
