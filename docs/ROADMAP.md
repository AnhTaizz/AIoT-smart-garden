# Kế hoạch 7 tuần

Tuần là số tương đối từ ngày nhóm bắt đầu, chưa gán ngày lịch. Ước lượng 10–12 giờ/người/tuần, chỉ lên task chính khoảng 6–8 giờ. Tích hợp mỗi 2–3 ngày; nghiệm thu vào cuối tuần.

Đích demo chính là **LOCAL MOBILE DEMO**. Laptop chạy toàn bộ React, FastAPI, Mosquitto và PostgreSQL; điện thoại và ESP32 cùng Wi-Fi/hotspot, truy cập laptop qua IP LAN. Public Internet deployment không phải điều kiện nghiệm thu và chỉ là stretch goal ở tuần 6. Luồng IoT end-to-end và điều khiển an toàn phải hoàn thành trước khi bắt đầu tích hợp AI. **Thay đổi phạm vi 2026-10-31:** bổ sung Weather-aware Auto Irrigation vào M3 (W3) theo yêu cầu chủ dự án; A (Thành) và C (Toản) cần review contract, lịch và tiêu chí. Weather không thay thế cảm biến đất hoặc quyền điều khiển cuối của ESP32. Kế hoạch triển khai chi tiết: [W3_WEATHER_LOCAL_EXECUTION_PLAN](W3_WEATHER_LOCAL_EXECUTION_PLAN.md).

## Việc chung trước khi tách task

| Mã | Chủ trì / kiểm tra | Thời lượng | Việc và đầu ra | Điều kiện hoàn thành |
| --- | --- | --- | --- | --- |
| G01 | Người điều phối / cả nhóm | 30 phút cả nhóm | Điền TEAM, chọn cây, chốt core/AI/ngoài phạm vi, mốc bắt đầu và giờ rảnh | Cả ba thống nhất; cập nhật PROJECT_STATE |
| G02 | Tài (B) / Thành (A) và Toản (C) | 60 phút cả nhóm | Chốt INTERFACES: telemetry, command, state/ack, API, lỗi và quyền điều khiển | Có ví dụ hợp lệ/lỗi; Thành và Toản xác nhận dùng được |
| G03 | Thành (A) / Tài (B) | 30 phút + theo dõi | BOM đủ nguồn, dây, ống và dụng cụ nạp; dự toán toàn bộ; mua core; lịch có camera | Có người mua, ngày nhận; chi phí được nhóm chốt; không coi đặt hàng là đã test |

G01–G02 đi trước task tích hợp; G03 triển khai song song tuần 1. Đây là công việc chung, ngoài 42 task cá nhân. Phụ thuộc G03 trong task phần cứng còn yêu cầu linh kiện thực sự đã tới.

## Phase và nghiệm thu

| Tuần | Phase | Mốc | Đầu ra | Tiêu chí |
| --- | --- | --- | --- | --- |
| 1 | Phase 1 — Luồng phần mềm | M1 | `Simulator → MQTT → backend subscriber → PostgreSQL → REST API → React → smartphone LAN`; chiều ngược qua FastAPI/MQTT tới simulator rồi ACK/state về UI. | Chỉ PASS khi toàn bộ checklist M1 dưới đây được chứng minh trong cùng một phiên end-to-end. G03 sẵn sàng cho tuần 2. |
| 2 | Phase 2 — Phần cứng thật | M2 | ESP32 thật đọc sensor, publish telemetry và điều khiển relay/bơm từ điện thoại. | Lưu hiệu chuẩn; smartphone gửi lệnh qua laptop; ESP32 ACK và bơm khởi động/tắt/tự dừng có giám sát; ghi log tích hợp thật. |
| 3 | Phase 2 — Điều khiển an toàn | M3 | Manual/Auto, tưới theo nhịp, safety, reconnect, **Weather-aware Auto** (dự báo mưa để hoãn tưới, có thể tắt). | Thử đất khô/ẩm, lỗi cảm biến, mất/reconnect Wi-Fi/MQTT, lệnh trùng/hết hạn và giới hạn bơm; thời tiết fresh/stale/unavailable, API lỗi, hoãn tưới có lý do và fallback; không để weather tự bật bơm. A+B+C review contract và có E2E trước nghiệm thu. |
| 4 | Phase 3 — Camera và AI baseline | M4 | ESP32-CAM → backend → xử lý ảnh; AI baseline có đánh giá ban đầu. | Có ảnh thật, split dữ liệu, phiên bản model, bảng kết quả và ví dụ lỗi; AI không tham gia quyết định bật bơm an toàn. |
| 5 | Phase 3 — Tích hợp đầy đủ | M5 | Một phiên bản tích hợp IoT, mobile dashboard, camera và AI. | Kiểm tra luồng thật và lỗi xử lý; inference không chặn telemetry/command; đóng phạm vi chức năng. |
| 6 | Phase 4 — Kiểm thử và hardening | M6 | Bản local mobile demo sẵn sàng bảo vệ, có số liệu và bằng chứng; cloud deploy chỉ optional. | Không còn lỗi nghiêm trọng về dừng bơm/điều khiển/luồng dữ liệu; thử kéo dài và nhiều tình huống mạng; nếu làm cloud phải tách khỏi độ tin cậy của demo local. |
| 7 | Phase 5 — Bàn giao | M7 | Repo + báo cáo + slide + video + kịch bản local mobile demo. | Khởi động lại theo README; diễn tập ít nhất hai lượt với smartphone/ESP32; có phương án hotspot dự phòng; giữ vài ngày cuối làm dự phòng. |

### Tiêu chí nghiệm thu bắt buộc của M1

Luồng thuận phải chạy trọn vẹn:

```text
Simulator → MQTT → backend subscriber → PostgreSQL
          → latest/history REST API → React → smartphone qua LAN
```

Luồng ngược phải chạy trọn vẹn:

```text
smartphone → React → FastAPI → MQTT command → simulator
           → ACK/state → backend → UI
```

M1 chỉ được ghi **PASS** khi có bằng chứng cho tất cả điều kiện sau trong cùng phiên bản:

- Telemetry từ simulator được backend subscriber nhận và lưu vào PostgreSQL.
- REST API latest và history trả đúng telemetry đã lưu.
- React hiển thị telemetry thật lấy từ API, không dùng số liệu giả.
- Điện thoại cùng LAN mở và sử dụng được dashboard qua IP LAN laptop.
- Mỗi command có `command_id` và giữ cùng ID xuyên suốt vòng đời.
- Simulator nhận được MQTT command.
- Simulator gửi cả ACK và state tương ứng về MQTT.
- Backend lưu/theo dõi và phân biệt `pending`, `applied`, `rejected`, `timeout`.
- UI chỉ báo áp dụng thành công sau ACK/state phù hợp; HTTP 2xx chỉ xác nhận backend đã nhận request.

PASS riêng lẻ của container, health endpoint, MQTT publish, API, UI hoặc LAN binding không được dùng thay bằng chứng end-to-end M1. `docs/INTERFACES.md` phải được cả 3 thành viên (Thành, Tài, Toản) xác nhận ở G02 trước nghiệm thu.

## Mở rộng W3 — dự báo thời tiết tham gia Auto (đề xuất chờ A/C review)

Chủ dự án yêu cầu đưa dự báo mưa vào W3, không lập roadmap BC mới và không thay 14 mã task của mỗi người. Trách nhiệm mới nằm ở **B-W3-01/02, A-W3-01/02, C-W3-01/02**:

- **B:** lấy Open-Meteo qua Backend (tọa độ cấu hình, cache/timeout/UTC, xác thực REST), hiển thị dữ liệu nguồn và tạo advisory `delay/no_delay/unknown` với TTL/lý do. Chưa publish dữ liệu weather sang firmware trước khi chốt G02.
- **A:** firmware vẫn giữ state machine/hysteresis, safety, STOP và quyền relay; dự báo fresh chỉ được **hoãn** chu kỳ Auto, không tự phát sinh ON; thử forecast lỗi, stale, reboot và reconnect.
- **C:** Weather Card và lý do tưới/hoãn tưới, phân biệt forecast với đo tại vườn; UI vẫn fail-closed khi mất auth/connection.
- **Nghiệm thu:** mở rộng các ca M3 nhưng vẫn giữ local mobile demo M1 và ESP32 thật M2 làm tiền đề. Ngưỡng mưa/ẩm đất phải hiệu chuẩn, không lấy số ví dụ làm mặc định. Thay đổi contract MQTT/REST phải được A+B+C duyệt.
- **Đánh đổi lịch:** các ước lượng W3 gốc không còn đủ cho tính năng mở rộng; đánh giá lại effort sau audit trên Claude Code local, không thu hẹp bài kiểm thử an toàn để giữ lịch.

**Thứ tự:** audit Git & môi trường local → kiểm thử baseline → cập nhật contract (DRAFT) → Weather API read-only + unit/E2E mock → dry-run advisory → A/C review → simulator → firmware/relay thật có giám sát → M3 nghiệm thu. Có feature flag để tắt Weather, không phá logic soil local.

Xem [kế hoạch triển khai W3 trên Claude Code local](W3_WEATHER_LOCAL_EXECUTION_PLAN.md).

## Luồng phụ thuộc chính

G02 → luồng mô phỏng/mobile LAN M1 → phần cứng thật M2 → Manual/Auto và safety M3 → camera/AI M4 → tích hợp M5 → hardening M6 → bàn giao M7.

M1–M3 là đường găng. Không chuyển nguồn lực sang tích hợp AI khi telemetry, command/ACK hoặc giới hạn an toàn của bơm còn lỗi nghiêm trọng. Camera, image API và AI baseline bắt đầu ở tuần 4 sau khi M3 có bằng chứng IoT end-to-end; nếu core trễ thì thu hẹp AI trước, không giảm tiêu chí an toàn. Public Internet deployment không nằm trên đường găng.

## Quy tắc điều chỉnh

- Giữa tuần 2 chưa có core hardware: Thành (A) đưa phương án mua/mượn/thay linh kiện; cả nhóm cập nhật lịch. M2 không được ghi PASS bằng simulator.
- Cuối tuần 3 chưa có IoT end-to-end ổn định: cả nhóm tiếp tục xử lý core và lùi/thu hẹp AI; ghi rõ ảnh hưởng lịch. Không giảm tiêu chí dừng bơm để chạy kịp.
- Tuần 4 nếu AI thiếu dữ liệu: thu hẹp nhãn hoặc đổi bài toán khả thi; ghi quyết định và cập nhật với thầy nếu thay cam kết. Không gọi HSV là mô hình học máy để thay phần còn thiếu.
- Cuối tuần 5 đóng phạm vi. Weather-aware Auto đã được đưa vào **phạm vi đề xuất M3 ngày 2026-10-31**, cần A+C duyệt phần giao tiếp và đo lại giờ công; các API thời tiết khác không liên quan Auto vẫn ngoài scope. Cloud deploy chỉ nhận ở tuần 6 nếu local mobile demo, core IoT và AI baseline đã đạt, có đủ người và thời gian kiểm thử.
- Tuần 6: mục tiêu đề xuất là một phiên theo dõi 4–8 giờ, khoảng 20 lệnh có giám sát, đủ tình huống lỗi quan trọng. Điều chỉnh theo điều kiện thiết bị, ghi đúng số lần và thời gian đã thử.
- Không dùng số liệu dự kiến thay kết quả. Chưa đo lượng nước và đối chứng thì chưa kết luận tiết kiệm nước. Chưa có cảm biến dòng chảy thì trạng thái relay không chứng minh nước đang chảy.

## Tài liệu viết xuyên suốt

Tuần 1: yêu cầu/kiến trúc. Tuần 2: mạch/hiệu chuẩn/schema. Tuần 3: logic tưới/kịch bản lỗi. Tuần 4: dataset/phương pháp AI. Tuần 5: tích hợp/hạn chế. Tuần 6: kết quả. Tuần 7: tổng hợp và diễn tập. Mỗi người bổ sung phần mình thực hiện sau nghiệm thu tuần.
