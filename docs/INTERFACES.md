# Thỏa thuận giao tiếp — Bản nháp cho G02

Trạng thái: **DRAFT — cả nhóm cần chốt ở G02 trước tích hợp**. Bản đề xuất cụ thể để chốt nằm ở mục [Bản đề xuất v1 của Tài (B)](#bản-đề-xuất-v1-của-tài-b--chờ-nhóm-chốt-ở-g02) cuối file. Tiêu chí nghiệm thu M1 đã được thống nhất trong kế hoạch, nhưng schema payload, response body, QoS/retained và xử lý lỗi vẫn chưa phải contract AGREED. Tài (B) chủ trì, Thành (A) và Toản (C) cùng kiểm tra. Chỉ đổi trạng thái sau khi có ví dụ hợp lệ/lỗi, ngày xác nhận và PR.

## Ranh giới xử lý

ESP32 giữ trạng thái tưới, đọc cảm biến, giới hạn chạy bơm và xử lý lỗi cục bộ. Backend kiểm tra yêu cầu, chuyển lệnh, lưu dữ liệu/sự kiện, cung cấp API. Frontend hiển thị trạng thái thiết bị xác nhận. Model chạy trên máy chủ và cung cấp kết quả ảnh; chưa đưa vào vòng điều khiển bơm.

## Luồng bắt buộc của M1

```text
Simulator → MQTT → backend subscriber → PostgreSQL
          → latest/history REST API → React → smartphone qua LAN

smartphone → React → FastAPI → MQTT command → simulator
           → ACK/state → backend → UI
```

Hai luồng phải chạy trên cùng phiên bản và cùng `device_id`. Kiểm tra riêng publisher/subscriber, database, API, UI hoặc LAN không đủ để nghiệm thu M1.

## MQTT cho M1

Giữ bốn topic hiện tại cho `node_01`; topic path được dùng thống nhất trong M1, còn chi tiết payload phải được cả 3 thành viên (Thành, Tài, Toản) xác nhận ở G02:

| Luồng | Topic M1 | Nội dung tối thiểu cần xác nhận |
| --- | --- | --- |
| Telemetry | garden/node_01/telemetry | device_id, boot_id/sequence nếu khử trùng, thời gian đo, giá trị/đơn vị, sensor_status, mode, relay_state |
| Command | garden/node_01/control | command_id, hành động, tham số, thời hạn; quy tắc kiểm tra tính hợp lệ |
| Xác nhận | garden/node_01/ack | command_id, accepted/rejected/applied, lý do và thời gian |
| Trạng thái | garden/node_01/state | device_id, mode/relay/cấu hình thực tế, last_command_id, thời gian báo trạng thái |

- Chốt QoS và retained cho từng topic. Không giữ retained lệnh bật bơm để thiết bị chạy lại lệnh cũ khi kết nối.
- Lệnh có ID để nhận biết trùng; nhận lại cùng ID không kéo dài giới hạn chạy. Chốt cửa sổ lưu ID và hành vi qua khởi động lại.
- Chốt cách từ chối lệnh hết hạn và xử lý khi đồng hồ thiết bị chưa đồng bộ. TTL không thay thế giới hạn thời gian chạy cục bộ.
- Backend/UI phân biệt yêu cầu đã gửi, thiết bị chấp nhận và trạng thái được áp dụng. ACK không chứng minh có dòng nước thật.
- Chốt ngưỡng xác định dữ liệu cũ/offline, cách lưu bản tin tới trễ và thứ tự bản tin.

## Vòng đời command bắt buộc cho M1

1. FastAPI nhận request hợp lệ, tạo/trả `command_id`, lưu trạng thái `pending` và publish cùng ID lên `garden/node_01/control`.
2. HTTP 2xx chỉ có nghĩa backend đã nhận request; frontend tiếp tục hiển thị `pending`, không báo thiết bị đã thực hiện.
3. Simulator nhận command và gửi ACK có cùng `command_id`. ACK `accepted` vẫn là trạng thái chờ; ACK `rejected` chuyển backend sang `rejected` và giữ lý do.
4. Khi áp dụng lệnh, simulator gửi ACK `applied` và state có `last_command_id` tương ứng cùng trạng thái thực tế. Backend chỉ chuyển sang `applied` khi thông tin nhận được khớp command.
5. Nếu không có kết quả cuối trong thời hạn đã chốt, backend chuyển sang `timeout`. ACK tới trễ phải được ghi nhận nhưng không được làm UI âm thầm báo thành công; cách hòa giải chi tiết chốt ở G02.

Backend và API phục vụ UI phải phân biệt tối thiểu bốn trạng thái `pending`, `applied`, `rejected`, `timeout`. Frontend hiển thị trạng thái backend trả về, không suy luận thành công từ mã HTTP của request tạo command.

## Dữ liệu và điều khiển

| Nội dung | Quyết định cần điền ở G02 |
| --- | --- |
| Thời gian | Chọn chuẩn UTC, độ chính xác, thời điểm nhận ở server và cách xử lý thời gian đo chưa hợp lệ |
| Đơn vị | Nhiệt độ °C, độ ẩm không khí %, đất là % tương đối sau hiệu chuẩn; giữ ADC phục vụ đánh giá khi cần |
| Sensor lỗi | null/status/error_code theo schema; không tự thay bằng 0 |
| Mode | AUTO/MANUAL, chuyển mode làm gì với bơm đang chạy; STOP ưu tiên ra sao |
| Giới hạn | Thời gian tối đa mỗi nhịp, tổng thời gian/số nhịp, thời gian chờ, điều kiện khóa khi lỗi |
| Cấu hình | Kiểm tra miền giá trị; requested khác applied; trạng thái sau reboot |
| Mực nước | Chỉ thêm nếu nhóm chốt có cảm biến thật; không tạo trường bắt buộc giả |

Ngưỡng tưới và thời lượng là tham số phải kiểm tra trên cây/chậu/bơm thực tế; tài liệu này không gán giá trị mặc định dùng ngay ngoài thực nghiệm.

## REST API bắt buộc cho M1 — dự kiến

| Nhu cầu | API gợi ý | Điều phải thống nhất |
| --- | --- | --- |
| Dữ liệu mới nhất | GET /devices/{id}/latest | sensor_status, timestamp, stale, mode, relay_state |
| Lịch sử | GET /devices/{id}/telemetry | from/to, giới hạn, thứ tự thời gian |
| Gửi lệnh | POST /devices/{id}/commands | kiểm tra input; trả command_id và pending, không trả thành công thiết bị |
| Theo dõi lệnh | GET /commands/{command_id} | pending/applied/rejected/timeout, ACK/state, lý do và ACK tới trễ |

`latest` và `history` phải đọc telemetry đã lưu trong PostgreSQL, không trả mock hoặc chỉ phản chiếu payload trong bộ nhớ. Điện thoại gọi các API qua cùng origin dashboard `/api`; FastAPI không cần expose trực tiếp ra LAN.

## API sau M1 — dự kiến

| Nhu cầu | API gợi ý | Điều phải thống nhất |
| --- | --- | --- |
| Cấu hình | GET/PUT /devices/{id}/config | requested/applied; phiên bản cấu hình |
| Upload ảnh | POST /devices/{id}/images | multipart, giới hạn file, metadata và image_id |
| Xem ảnh/kết quả | GET /devices/{id}/images | image_id, captured_at, trạng thái xử lý, model_version, kết quả/lỗi |

Tuần 1 dùng polling đơn giản hoặc cơ chế nhóm quen thuộc; chốt một cách. Chưa cần thêm WebSocket nếu không giải quyết vấn đề thực tế. Phần ảnh được hoàn thiện chi tiết trước tuần 4; thống nhất mã thiết bị và thời gian ngay tuần 1.

## Hợp đồng model — chốt ở tuần 3–4

Toản (C) bàn giao Tài (B): artifact model, preprocessing, danh sách nhãn, inference mẫu, phiên bản dataset/model, dependency, kích thước ảnh và lỗi đầu vào. Tài trả kết quả gắn image_id và model_version. HSV trả độ phủ xanh riêng; model phân loại trả nhãn/điểm mô hình riêng. Không tự gọi điểm mô hình là xác suất đã hiệu chuẩn.

## Bản đề xuất v1 của Tài (B) — chờ nhóm chốt ở G02

Trạng thái mục này: **DRAFT**. Backend và simulator trong nhánh `feat/B-W1-backend-telemetry-command` đã triển khai đúng các quy tắc dưới đây để nhóm có thứ cụ thể kiểm tra, nhưng chưa ai xác nhận. Thành (A) xem phần thiết bị, Toản (C) xem phần REST/UI; mọi thay đổi phải sửa cả mục này và code trong cùng PR.

### 1. Quy ước chung

Topic `garden/<device_id>/<kind>`. `device_id` và `boot_id` chỉ gồm `A-Z a-z 0-9 _ -`, dài 1–64 ký tự. `device_id` trong payload phải trùng `device_id` trong topic, nếu lệch thì bản tin bị từ chối.

| Topic | Hướng | QoS | Retained | Session |
| --- | --- | --- | --- | --- |
| `garden/<id>/telemetry` | thiết bị → backend | 0 | không | clean |
| `garden/<id>/control` | backend → thiết bị | 1 | **không** | clean |
| `garden/<id>/ack` | thiết bị → backend | 1 | không | clean |
| `garden/<id>/state` | thiết bị → backend | 1 | không | clean |

`clean_session = true` (MQTT 5: `clean_start = true`, không session expiry) là **bắt buộc ở cả hai phía** và phải đặt tường minh trong code, không dựa vào mặc định thư viện. Broker không được giữ lệnh cho thiết bị đang offline: đây là tuyến phòng thủ chính chống lệnh cũ được giao lại sau khi thiết bị kết nối lại.

Thời gian dùng ISO 8601 có múi giờ; backend luôn phát UTC dạng `2026-09-25T09:11:00.000Z`.

**Trục thời gian của M1 là `received_at` do backend gán khi nhận bản tin.** `latest` và `history` sắp xếp theo `received_at`. `measured_at`/`reported_at`/`acked_at` là thời điểm thiết bị tự báo, chỉ để hiển thị và đối chiếu; thiết bị chưa đồng bộ giờ thì các trường này là `null`.

### 2. `telemetry-v1`

```json
{
  "schema": "telemetry-v1",
  "simulated": true,
  "device_id": "node_01",
  "boot_id": "boot_9c1f0b1f",
  "sequence": 42,
  "clock_synced": true,
  "measured_at": "2026-09-25T09:10:00.000Z",
  "uptime_ms": 812345,
  "temperature_c": 27.5,
  "air_humidity_pct": 60.1,
  "soil_moisture_pct": 42.0,
  "sensor_status": {"aht20": "ok", "soil": "ok"}
}
```

| Trường | Kiểu | Bắt buộc | Ghi chú |
| --- | --- | --- | --- |
| `schema` | string | có | Giá trị cố định `telemetry-v1` |
| `simulated` | bool | có | `true` cho simulator, `false` cho ESP32 thật |
| `device_id` | string | có | Khớp topic |
| `boot_id` | string | có | Đổi mỗi lần thiết bị khởi động |
| `sequence` | int ≥ 1 | có | Tăng 1 trong một boot, reset khi boot mới |
| `clock_synced` | bool | có | Thiết bị có giờ UTC đáng tin cậy hay không |
| `measured_at` | string \| null | có | ISO có múi giờ khi `clock_synced: true`; **phải** là `null` khi `false` |
| `uptime_ms` | int ≥ 0 | có | Thời gian chạy từ lúc boot, luôn có |
| `temperature_c` | number \| null | có | −40…85 °C; `null` khi cảm biến lỗi |
| `air_humidity_pct` | number \| null | có | 0…100 % |
| `soil_moisture_pct` | number \| null | có | 0…100 %, thang tương đối sau hiệu chuẩn |
| `sensor_status` | object | có | Khóa `aht20` và `soil`, giá trị `"ok"` hoặc `"error"` |

Ràng buộc bắt buộc, backend kiểm tra và từ chối nếu vi phạm:

- `sensor_status.aht20 = "error"` ⇔ `temperature_c` và `air_humidity_pct` đều `null`.
- `sensor_status.soil = "error"` ⇔ `soil_moisture_pct` là `null`.
- Không bao giờ thay giá trị lỗi bằng `0`.
- Trùng `device_id` + `boot_id` + `sequence`: backend **bỏ qua im lặng**, không lưu hai lần và **không** coi là bản tin lỗi.

Ví dụ bị từ chối và ghi vào bảng `rejected_message`: JSON hỏng; `"sequence": "42"`; `"air_humidity_pct": 250`; `NaN`; `measured_at` thiếu múi giờ; `clock_synced: false` nhưng vẫn có `measured_at`; `temperature_c: null` trong khi `sensor_status.aht20 = "ok"`; `device_id` khác topic.

### 3. `command-v1`

Backend publish lên `garden/<device_id>/control`, QoS 1, không retained.

```json
{
  "schema": "command-v1",
  "command_id": "253b7b9c-aafe-4fdd-bc95-ae55b3d41068",
  "device_id": "node_01",
  "command_sequence": 7,
  "action": "pump_on",
  "params": {"duration_seconds": 10},
  "target_boot_id": "boot_9c1f0b1f",
  "issued_at": "2026-09-25T09:11:00.000Z",
  "expires_at": "2026-09-25T09:11:15.000Z"
}
```

```json
{
  "schema": "command-v1",
  "command_id": "9b2e41d0-5f27-4a3c-8f10-6d4b7a2c9e55",
  "device_id": "node_01",
  "command_sequence": 8,
  "action": "pump_off",
  "params": {},
  "target_boot_id": null,
  "issued_at": "2026-09-25T09:11:20.000Z",
  "expires_at": "2026-09-25T09:11:35.000Z"
}
```

| Trường | Kiểu | Ghi chú |
| --- | --- | --- |
| `schema` | string | Bắt buộc, giá trị cố định `command-v1` |
| `command_id` | UUID string | Bắt buộc, giữ nguyên qua command/ACK/state/REST |
| `device_id` | string | Bắt buộc, khớp `<device_id>` trong topic |
| `command_sequence` | int ≥ 1 | Tăng theo từng thiết bị, backend cấp nguyên tử và lưu trong PostgreSQL nên không reset khi backend restart |
| `action` | `pump_on` \| `pump_off` | M1 chỉ có hai action này |
| `params` | object | `pump_on`: `{"duration_seconds": 1..120}`. `pump_off`: `{}` |
| `target_boot_id` | string \| null | Bắt buộc có giá trị cho `pump_on` (boot mà backend đang biết). Luôn `null` cho `pump_off` |
| `issued_at` | ISO 8601 string | Bắt buộc, UTC do backend gán |
| `expires_at` | ISO 8601 string | Bắt buộc, hạn tuyệt đối. **Không có** `ttl_seconds` |

**Tại sao không dùng TTL đếm từ lúc nhận:** TTL chỉ giới hạn khoảng từ *lúc thiết bị nhận* tới *lúc bắt đầu chạy*, nó không biết bản tin đã nằm chờ bao lâu trước đó. Lệnh phát 14:00, thiết bị nhận 14:03 thì TTL 15 giây vẫn cho phép chạy một lệnh đã cũ 3 phút. Vì vậy hạn duy nhất là `expires_at` tuyệt đối, và `pump_on` chỉ được thực thi khi thiết bị kiểm tra được hạn đó.

`duration_seconds` 1–120 là **giới hạn kiểm tra đầu vào của API**, không phải thời lượng tưới mặc định. Thiết bị giữ giới hạn cứng riêng của nó, xác định bằng thử nghiệm bơm/chậu thật; thiết bị được phép từ chối `invalid_duration` nếu vượt giới hạn cục bộ.

### 4. `ack-v1`

```json
{
  "schema": "ack-v1",
  "command_id": "253b7b9c-aafe-4fdd-bc95-ae55b3d41068",
  "device_id": "node_01",
  "boot_id": "boot_9c1f0b1f",
  "status": "applied",
  "reason": null,
  "clock_synced": true,
  "acked_at": "2026-09-25T09:11:01.200Z"
}
```

| Trường | Kiểu | Bắt buộc/nullable | Ghi chú |
| --- | --- | --- | --- |
| `schema` | string | có, không null | Giá trị cố định `ack-v1` |
| `command_id` | UUID string | có, không null | Command được trả lời |
| `device_id` | string | có, không null | Khớp topic và command |
| `boot_id` | string | có, không null | Boot phát ACK |
| `status` | `accepted` \| `applied` \| `rejected` | có, không null | `accepted` chỉ là đã nhận, chưa chứng minh output |
| `reason` | reason enum \| null | có, nullable | Bắt buộc có mã ở mục 8 khi `rejected`; phải `null` với `accepted`/`applied` |
| `clock_synced` | bool | có, không null | Giờ UTC của thiết bị có đáng tin cậy hay không |
| `acked_at` | ISO 8601 string \| null | có, nullable | Có giá trị đúng khi `clock_synced: true`; phải `null` khi `false` |

`boot_id` cho phép backend nhận ra ACK phát từ một boot đã chết. ACK sai `schema`, sai UUID, reason ngoài enum hoặc cặp `clock_synced`/`acked_at` mâu thuẫn bị từ chối.

### 5. `state-v1`

```json
{
  "schema": "state-v1",
  "device_id": "node_01",
  "boot_id": "boot_9c1f0b1f",
  "state_sequence": 128,
  "mode": "MANUAL",
  "relay_state": "on",
  "last_command_id": "253b7b9c-aafe-4fdd-bc95-ae55b3d41068",
  "last_command_sequence": 7,
  "clock_synced": true,
  "reported_at": "2026-09-25T09:11:01.300Z",
  "uptime_ms": 812350
}
```

| Trường | Kiểu | Bắt buộc/nullable | Ghi chú |
| --- | --- | --- | --- |
| `schema` | string | có, không null | Giá trị cố định `state-v1` |
| `device_id` | string | có, không null | Khớp topic |
| `boot_id` | string | có, không null | Boot phát state |
| `state_sequence` | int ≥ 1 | có, không null | Tăng 1 trong một boot |
| `mode` | `MANUAL` \| `AUTO` | có, không null | M1 chỉ dùng `MANUAL`; giữ enum `AUTO` cho M3 |
| `relay_state` | `on` \| `off` | có, không null | Output relay do thiết bị tự báo |
| `last_command_id` | UUID string \| null | có, nullable | Command cuối cùng thiết bị đã áp dụng |
| `last_command_sequence` | int ≥ 1 \| null | có, nullable | Phải cùng có hoặc cùng null với `last_command_id` |
| `clock_synced` | bool | có, không null | Giờ UTC của thiết bị có đáng tin cậy hay không |
| `reported_at` | ISO 8601 string \| null | có, nullable | Có giá trị đúng khi `clock_synced: true`; phải `null` khi `false` |
| `uptime_ms` | int ≥ 0 | có, không null | Thời gian chạy từ lúc boot |

Thiết bị phát state: ngay sau khi kết nối, ngay sau khi xử lý mỗi command, khi bơm tự tắt hết thời lượng, và heartbeat mỗi 10 giây.

### 6. Quy tắc thiết bị (ESP32 và simulator)

Thứ tự kiểm tra một command, dừng ở bước đầu tiên không đạt:

1. **Đọc payload.** Không parse được hoặc không có `command_id` UUID hợp lệ: bỏ qua, chỉ ghi log thiết bị. Parse được nhưng sai `schema`, thiếu trường hoặc sai kiểu ở envelope chung: ACK `rejected` + `invalid_payload`.
2. **`device_id` khác thiết bị:** bỏ qua, không ACK.
3. **Trùng `command_id`** trong boot hiện tại: phát lại **đúng ACK cũ**, không chạy lại, không gia hạn bộ đếm bơm.
4. **`action` không hỗ trợ:** `unsupported_action`.
5. **`pump_on` thiếu hoặc sai `duration_seconds`,** hoặc vượt giới hạn cục bộ: `invalid_duration`.
6. **`pump_on` có `target_boot_id` khác `boot_id` hiện tại** (hoặc thiếu): `boot_mismatch`.
7. **`pump_on` khi chưa có giờ đáng tin cậy:** `clock_unsynced`. Có giờ và `expires_at` đã qua: `expired`.
8. **`pump_on` có `command_sequence` ≤ mốc thứ tự (`order_mark`):** `superseded`.
9. **`pump_on` khi đang chạy một `command_id` khác:** `busy`.
10. **Relay/an toàn lỗi:** `relay_error` hoặc `safety_lock`.
11. Thực thi, cập nhật `order_mark = max(order_mark, command_sequence)`, ACK `applied`, phát state.

`pump_off` **bỏ qua bước 6–9**: OFF không bị boot đích, đồng hồ, hạn hay `busy` chặn, và OFF khi relay vốn đã tắt vẫn trả `applied` kèm state tương ứng. Lý do: tắt bơm luôn an toàn hơn để bơm chạy.

`order_mark` là mốc thứ tự chỉ tăng, lưu trong RAM của boot hiện tại: nó được nâng lên mỗi khi thiết bị áp dụng một command bất kỳ, và một OFF cũ hoặc trùng không bao giờ làm nó lùi. Nhờ vậy một ON phát trước OFF nhưng đến sau OFF sẽ bị `superseded`, không bật bơm.

Sau reboot: relay về `off`, `order_mark` về 0, bộ nhớ `command_id` trống, `boot_id` mới. Thiết bị không khôi phục lệnh ON cũ. Mất MQTT thì tắt bơm (M1/M2).

### 7. Quy tắc backend

**Điều kiện `applied` — cần hai bằng chứng độc lập:**

1. ACK `applied` có cùng `command_id` và `device_id`; với `pump_on` thì `boot_id` của ACK phải bằng `target_boot_id`.
2. Một state có `last_command_id` bằng `command_id`, cùng `boot_id` với ACK, và `relay_state` khớp hành động: `on` cho `pump_on`, `off` cho `pump_off`.

Hai bằng chứng đến theo thứ tự nào cũng được; cái đến sau chốt trạng thái `applied`. Bằng chứng được lưu **theo từng command** (`state_confirmed_at`, `confirmed_relay_state`, `confirmed_state_sequence`, `confirmed_boot_id`), tách khỏi state mới nhất của thiết bị. Nhờ vậy một lệnh ON 5 giây vẫn `applied` sau khi bơm tự tắt, trong khi `GET /devices/{id}/state` hiển thị `relay_state: "off"` hiện tại. State mới không xóa bằng chứng cũ.

Chỉ nhận được state `off` mà chưa có bằng chứng `on` phù hợp thì **không** kết luận `pump_on` đã `applied`.

`applied` chỉ xác nhận thiết bị báo đã bật/tắt đầu ra relay. Nó **không** chứng minh có nước thực sự chảy; muốn kết luận điều đó cần cảm biến dòng/mực nước thật và nhóm chưa chốt có phần cứng đó.

**Boot:**

- Backend học `boot_id` từ state. State có `boot_id` chưa từng thấy là một boot mới: ghi nhận và đặt làm boot hiện tại.
- Khi boot hiện tại đổi từ boot cũ sang boot mới, mọi command còn `pending` có `target_boot_id` bằng boot cũ chuyển sang `timeout` với `reason: "backend:device_rebooted"`. Lần đầu backend biết boot của thiết bị **không** phải reboot nên không kết thúc command nào.
- Command `pump_off` (`target_boot_id` là `null`) vẫn giữ `pending` qua reboot, vì boot mới vẫn có thể áp dụng nó.
- State có `boot_id` đã biết nhưng không phải boot hiện tại là bản tin muộn của boot cũ: **không** cập nhật state hiện tại của thiết bị (không quay lại boot cũ), nhưng vẫn dùng được làm bằng chứng cho command thuộc boot đó.
- ACK có `boot_id` là một boot đã biết nhưng không phải boot hiện tại, hoặc không khớp `target_boot_id` của command: ghi nhận là muộn/cũ, không đổi trạng thái command.

**Thứ tự state:** trong cùng `boot_id`, state có `state_sequence` ≤ giá trị đã lưu bị bỏ qua cho mục đích cập nhật state hiện tại.

**Timeout:** chưa đủ hai bằng chứng khi quá `expires_at` thì command thành `timeout`. ACK đến sau được ghi vào `late_ack`/`late_ack_at`. State muộn khớp action/boot được giữ trong các cột `state_confirmed_*` của command; nếu state đó mới hơn thì nó vẫn cập nhật state hiện tại. Mọi ACK/state muộn còn có bản ghi `command_event` chứa `command_id`, `device_id`, `boot_id`, outcome và payload. Các bằng chứng này không đổi `timeout` thành `applied`. `timeout` **không** có nghĩa bơm đã tắt.

**Thứ tự command:** `command_sequence` cấp theo thiết bị bằng một câu UPDATE nguyên tử trên bảng `device_command_counter` trong PostgreSQL, nên không trùng và không lùi khi backend restart.

**`pump_on` cần boot đã biết:** khi backend chưa nhận state nào của thiết bị, `POST` `pump_on` trả `409 device_boot_unknown` và không tạo command, vì không thể gắn `target_boot_id`. `pump_off` không cần boot.

### 8. Bảng reason

Tiền tố cho biết bên nào phát ra, để UI không nói "thiết bị từ chối" khi thực ra backend lỗi.

| Reason | Bên phát | Khi nào |
| --- | --- | --- |
| `invalid_payload` | thiết bị | Payload command thiếu trường hoặc sai kiểu |
| `unsupported_action` | thiết bị | Action ngoài `pump_on`/`pump_off` |
| `invalid_duration` | thiết bị | `duration_seconds` thiếu hoặc vượt giới hạn cục bộ |
| `boot_mismatch` | thiết bị | `target_boot_id` khác `boot_id` hiện tại của thiết bị |
| `clock_unsynced` | thiết bị | `pump_on` nhưng thiết bị chưa có giờ đáng tin cậy để kiểm tra hạn |
| `expired` | thiết bị | `expires_at` đã qua khi thiết bị xử lý |
| `superseded` | thiết bị | `pump_on` có `command_sequence` ≤ mốc thứ tự, thường vì một OFF mới hơn đã được áp dụng |
| `busy` | thiết bị | `pump_on` khác đang chạy |
| `safety_lock` | thiết bị | Thiết bị đang tự khóa sau sự cố |
| `relay_error` | thiết bị | Không điều khiển được relay |
| `sensor_error` | thiết bị | Dành cho AUTO ở M3 |
| `internal_error` | thiết bị | Lỗi khác, kèm log phía thiết bị |
| `backend:publish_failed` | backend | Không publish được lệnh lên broker |
| `backend:device_rebooted` | backend | Thiết bị báo boot mới khi command của boot cũ còn `pending` |

**Lỗi cảm biến và lệnh tay:** trong phạm vi demo hiện tại (M1–M2, chỉ MANUAL, chỉ AHT20 và cảm biến đất điện dung), lỗi AHT20 hoặc lỗi cảm biến đất **không** chặn `pump_on`, vì người bấm nút đang chịu trách nhiệm và chặn lệnh tay sẽ lấy đi khả năng can thiệp. Đây là lựa chọn cho đúng bộ cảm biến này, **không** phải quy tắc chung: một cảm biến an toàn thật sự (mực nước, dòng chảy, quá nhiệt, quá dòng) nếu được thêm vào BOM thì phải chặn ON, và nhóm chốt lại ở G03/M3. `sensor_error` chặn ON trong AUTO từ M3 khi máy tự quyết định tưới. Không có lỗi cảm biến nào được chặn `pump_off`.

### 9. REST

Backend chỉ phục vụ qua cùng origin dashboard `/api`. Mọi lỗi dùng chung một dạng thân phản hồi, kể cả 422:

```json
{"detail": {"code": "no_telemetry", "message": "Thiết bị chưa có telemetry nào được lưu."}}
```

`GET /devices/node_01/latest` → `200`:

```json
{
  "id": 41,
  "device_id": "node_01",
  "boot_id": "boot_9c1f0b1f",
  "sequence": 42,
  "clock_synced": true,
  "measured_at": "2026-09-25T09:10:00.000Z",
  "received_at": "2026-09-25T09:10:00.142Z",
  "uptime_ms": 812345,
  "temperature_c": 27.5,
  "air_humidity_pct": 60.1,
  "soil_moisture_pct": 42.0,
  "sensor_status": {"aht20": "ok", "soil": "ok"},
  "simulated": true,
  "payload_schema": "telemetry-v1",
  "stale": false,
  "stale_after_seconds": 30
}
```

`GET /devices/node_01/telemetry?from=2026-09-25T09:00:00Z&to=2026-09-25T09:30:00Z&limit=100&order=asc` → `200`:

```json
{
  "device_id": "node_01",
  "count": 2,
  "order": "asc",
  "items": [
    {
      "id": 40,
      "device_id": "node_01",
      "boot_id": "boot_9c1f0b1f",
      "sequence": 41,
      "clock_synced": true,
      "measured_at": "2026-09-25T09:09:58.000Z",
      "received_at": "2026-09-25T09:09:58.132Z",
      "uptime_ms": 810345,
      "temperature_c": 27.4,
      "air_humidity_pct": 60.0,
      "soil_moisture_pct": 42.2,
      "sensor_status": {"aht20": "ok", "soil": "ok"},
      "simulated": true,
      "payload_schema": "telemetry-v1"
    },
    {
      "id": 41,
      "device_id": "node_01",
      "boot_id": "boot_9c1f0b1f",
      "sequence": 42,
      "clock_synced": true,
      "measured_at": "2026-09-25T09:10:00.000Z",
      "received_at": "2026-09-25T09:10:00.142Z",
      "uptime_ms": 812345,
      "temperature_c": 27.5,
      "air_humidity_pct": 60.1,
      "soil_moisture_pct": 42.0,
      "sensor_status": {"aht20": "ok", "soil": "ok"},
      "simulated": true,
      "payload_schema": "telemetry-v1"
    }
  ]
}
```

Backend chọn `limit` bản ghi **mới nhất** theo `received_at` trong khoảng, rồi sắp theo `order` (`asc` mặc định). History không có trường `stale`; `from`/`to` phải có múi giờ. `count == limit` chỉ cho biết **có thể** còn bản ghi cũ hơn, không khẳng định chắc chắn; phân trang bằng con trỏ để sau M1.

`POST /devices/node_01/commands` với `{"action": "pump_on", "duration_seconds": 10}` → `202`:

```json
{
  "command_id": "253b7b9c-aafe-4fdd-bc95-ae55b3d41068",
  "device_id": "node_01",
  "command_sequence": 7,
  "action": "pump_on",
  "params": {"duration_seconds": 10},
  "target_boot_id": "boot_9c1f0b1f",
  "status": "pending",
  "device_ack": null,
  "reason": null,
  "created_at": "2026-09-25T09:11:00.000Z",
  "expires_at": "2026-09-25T09:11:15.000Z",
  "published_at": "2026-09-25T09:11:00.012Z",
  "acked_at": null,
  "ack_boot_id": null,
  "state_confirmed_at": null,
  "confirmed_relay_state": null,
  "confirmed_state_sequence": null,
  "confirmed_boot_id": null,
  "finalized_at": null,
  "late_ack": null,
  "late_ack_at": null
}
```

**`202` chỉ có nghĩa backend đã nhận và publish yêu cầu.** UI giữ trạng thái "đang chờ thiết bị", poll `GET /commands/{command_id}` mỗi 1 giây trong lúc `pending` và dừng ngay khi trạng thái là final hoặc sau 30 giây.

`GET /commands/253b7b9c-aafe-4fdd-bc95-ae55b3d41068` → `200`, cùng dạng trên, ví dụ sau khi có đủ hai bằng chứng:

```json
{
  "command_id": "253b7b9c-aafe-4fdd-bc95-ae55b3d41068",
  "device_id": "node_01",
  "command_sequence": 7,
  "action": "pump_on",
  "params": {"duration_seconds": 10},
  "target_boot_id": "boot_9c1f0b1f",
  "status": "applied",
  "device_ack": "applied",
  "reason": null,
  "created_at": "2026-09-25T09:11:00.000Z",
  "expires_at": "2026-09-25T09:11:15.000Z",
  "published_at": "2026-09-25T09:11:00.012Z",
  "acked_at": "2026-09-25T09:11:01.210Z",
  "ack_boot_id": "boot_9c1f0b1f",
  "state_confirmed_at": "2026-09-25T09:11:01.350Z",
  "confirmed_relay_state": "on",
  "confirmed_state_sequence": 128,
  "confirmed_boot_id": "boot_9c1f0b1f",
  "finalized_at": "2026-09-25T09:11:01.350Z",
  "late_ack": null,
  "late_ack_at": null
}
```

`GET /devices/node_01/commands?limit=20` → `200`:

```json
{
  "device_id": "node_01",
  "count": 1,
  "items": [
    {
      "command_id": "253b7b9c-aafe-4fdd-bc95-ae55b3d41068",
      "device_id": "node_01",
      "command_sequence": 7,
      "action": "pump_on",
      "params": {"duration_seconds": 10},
      "target_boot_id": "boot_9c1f0b1f",
      "status": "applied",
      "device_ack": "applied",
      "reason": null,
      "created_at": "2026-09-25T09:11:00.000Z",
      "expires_at": "2026-09-25T09:11:15.000Z",
      "published_at": "2026-09-25T09:11:00.012Z",
      "acked_at": "2026-09-25T09:11:01.210Z",
      "ack_boot_id": "boot_9c1f0b1f",
      "state_confirmed_at": "2026-09-25T09:11:01.350Z",
      "confirmed_relay_state": "on",
      "confirmed_state_sequence": 128,
      "confirmed_boot_id": "boot_9c1f0b1f",
      "finalized_at": "2026-09-25T09:11:01.350Z",
      "late_ack": null,
      "late_ack_at": null
    }
  ]
}
```

`GET /devices/node_01/state` → `200`:

```json
{
  "device_id": "node_01",
  "boot_id": "boot_9c1f0b1f",
  "state_sequence": 131,
  "mode": "MANUAL",
  "relay_state": "off",
  "last_command_id": "253b7b9c-aafe-4fdd-bc95-ae55b3d41068",
  "last_command_sequence": 7,
  "clock_synced": true,
  "reported_at": "2026-09-25T09:11:11.400Z",
  "received_at": "2026-09-25T09:11:11.430Z",
  "stale": false,
  "stale_after_seconds": 30
}
```

| Tình huống | Mã HTTP | `code` |
| --- | --- | --- |
| Chưa có telemetry của thiết bị | 404 | `no_telemetry` |
| Chưa nhận state nào của thiết bị | 404 | `no_state` |
| Không tìm thấy command | 404 | `command_not_found` |
| Body/tham số/`command_id` sai | 422 | `invalid_payload` |
| `pump_on` khi backend chưa biết boot | 409 | `device_boot_unknown` |
| Backend mất kết nối broker | 503 | `mqtt_unavailable` |
| Publish thất bại sau khi đã tạo command | 503 | `backend_publish_failed`, command thành `rejected` với `reason: "backend:publish_failed"` |
| PostgreSQL không dùng được | 503 | `database_unavailable` |

UI hiển thị 404 `no_telemetry`/`no_state` là trạng thái rỗng ("chưa có dữ liệu"), không phải lỗi hệ thống.

### 10. Tham số thời gian của M1

| Tham số | Giá trị | Biến môi trường |
| --- | --- | --- |
| Nhịp telemetry | 2–5 giây | `TELEMETRY_INTERVAL_SECONDS` (simulator) |
| Heartbeat state | 10 giây | `STATE_HEARTBEAT_SECONDS` (simulator) |
| Ngưỡng telemetry/state cũ | 30 giây | `TELEMETRY_STALE_SECONDS` (backend) |
| Hạn command | 15 giây kể từ `issued_at` | `COMMAND_TIMEOUT_SECONDS` (backend) |
| `duration_seconds` cho phép ở API | 1–120 giây | `COMMAND_MAX_DURATION_SECONDS` (backend) |
| Giới hạn chạy bơm cục bộ | thiết bị tự giữ, chốt bằng thử nghiệm thật | `PUMP_MAX_SECONDS` (simulator) |

### 11. Đồng bộ giờ cho ESP32 — đầu việc trước M2

Vì `pump_on` chỉ được thực thi khi thiết bị kiểm tra được `expires_at`, ESP32 phải có giờ UTC đáng tin cậy trước khi điều khiển bơm thật. Hiện tại **chưa có** cơ chế nào được triển khai; đây là đầu việc phải chốt trước M2, không phải điều đã làm:

- Simulator ở M1 chạy trên laptop và dùng giờ hệ điều hành, nên `clock_synced` là `true` và luồng M1 không chờ việc này.
- Phương án cho ESP32, chọn một và ghi lại: SNTP tới Internet nếu Wi-Fi demo có Internet; hoặc chạy một dịch vụ NTP/SNTP ngay trên laptop trong LAN demo và trỏ ESP32 vào IP LAN đó; hoặc backend phát thêm một bản tin thời gian trên MQTT để thiết bị đặt giờ.
- Không được mặc định demo có Internet, và không tuyên bố đã đồng bộ khi thiết bị vẫn báo `clock_synced: false`.
- Trong khi chưa có giờ, thiết bị vẫn publish telemetry với `measured_at: null` và vẫn thực thi `pump_off`; chỉ `pump_on` bị từ chối bằng `clock_unsynced`.

### 12. Để sau M1

Phân trang bằng con trỏ cho history; AUTO và API cấu hình (M3); khử trùng theo thời gian đến trễ; xác thực API/MQTT; ảnh và inference (M4); WebSocket nếu polling thực sự không đủ.

### 13. Điều kiện để đổi mục này thành AGREED

| Điều kiện | Trạng thái |
| --- | --- |
| Bảng topic/QoS/retained/session | có |
| Bốn payload v1 kèm ví dụ hợp lệ và ví dụ bị từ chối | có |
| Thứ tự kiểm tra của thiết bị và quy tắc backend | có |
| Bảng reason ghi rõ bên phát | có |
| Sáu endpoint REST kèm mẫu response và bảng mã lỗi | có |
| Thành (A) xác nhận thiết bị/firmware làm được | **chưa** |
| Toản (C) xác nhận REST/UI đủ dữ liệu | **chưa** |
| Tài (B) xác nhận backend đúng bản này | **chưa** |
| Ghi tên, ngày và link PR ở mục Xác nhận; đổi DRAFT → AGREED trong PR có cả ba approve | **chưa** |

G02 AGREED là điều kiện đi trước và **không** đồng nghĩa M1 PASS. M1 PASS vẫn theo đúng checklist trong [ROADMAP](ROADMAP.md): cần một phiên end-to-end có telemetry lên UI, command quay về thiết bị, và điện thoại thật mở dashboard qua IP LAN.

## Xác nhận

Thành (A): chưa xác nhận. Tài (B): chưa xác nhận. Toản (C): chưa xác nhận. Link PR thống nhất: chưa có.
