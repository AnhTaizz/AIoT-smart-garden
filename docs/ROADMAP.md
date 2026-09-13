# Kế hoạch 7 tuần

Tuần là số tương đối từ ngày nhóm bắt đầu, chưa gán ngày lịch. Ước lượng 10–12 giờ/người/tuần, chỉ lên task chính khoảng 6–8 giờ. Tích hợp mỗi 2–3 ngày; nghiệm thu vào cuối tuần.

Đích demo chính là **LOCAL MOBILE DEMO**. Laptop chạy toàn bộ React, FastAPI, Mosquitto và PostgreSQL; điện thoại và ESP32 cùng Wi-Fi/hotspot, truy cập laptop qua IP LAN. Public Internet deployment không phải điều kiện nghiệm thu và chỉ là stretch goal ở tuần 6. Luồng IoT end-to-end và điều khiển an toàn phải hoàn thành trước khi bắt đầu tích hợp AI. Weather API không thuộc core scope.

## Việc chung trước khi tách task

| Mã | Chủ trì / kiểm tra | Thời lượng | Việc và đầu ra | Điều kiện hoàn thành |
| --- | --- | --- | --- | --- |
| G01 | Người điều phối / cả nhóm | 30 phút cả nhóm | Điền TEAM, chọn cây, chốt core/AI/ngoài phạm vi, mốc bắt đầu và giờ rảnh | Cả ba thống nhất; cập nhật PROJECT_STATE |
| G02 | B / A và C | 60 phút cả nhóm | Chốt INTERFACES: telemetry, command, state/ack, API, lỗi và quyền điều khiển | Có ví dụ hợp lệ/lỗi; A và C xác nhận dùng được |
| G03 | A / B | 30 phút + theo dõi | BOM đủ nguồn, dây, ống và dụng cụ nạp; dự toán toàn bộ; mua core; lịch có camera | Có người mua, ngày nhận; chi phí được nhóm chốt; không coi đặt hàng là đã test |

G01–G02 đi trước task tích hợp; G03 triển khai song song tuần 1. Đây là công việc chung, ngoài 42 task cá nhân. Phụ thuộc G03 trong task phần cứng còn yêu cầu linh kiện thực sự đã tới.

## Phase và nghiệm thu

| Tuần | Phase | Mốc | Đầu ra | Tiêu chí |
| --- | --- | --- | --- | --- |
| 1 | Phase 1 — Luồng phần mềm | M1 | Simulator → MQTT → PostgreSQL → API → React → smartphone qua LAN; command ngược lại có ACK/state. | G01–G02 được chốt; điện thoại khác mở được dashboard bằng IP LAN laptop; telemetry mô phỏng được lưu/hiển thị; command và ACK phân biệt đúng. G03 sẵn sàng cho tuần 2. |
| 2 | Phase 2 — Phần cứng thật | M2 | ESP32 thật đọc sensor, publish telemetry và điều khiển relay/bơm từ điện thoại. | Lưu hiệu chuẩn; smartphone gửi lệnh qua laptop; ESP32 ACK và bơm khởi động/tắt/tự dừng có giám sát; ghi log tích hợp thật. |
| 3 | Phase 2 — Điều khiển an toàn | M3 | Manual/Auto, tưới theo nhịp, safety, reconnect và error handling. | Thử đất khô/ẩm, lỗi cảm biến, mất/reconnect Wi-Fi hoặc MQTT, lệnh trùng/hết hạn và giới hạn chạy bơm; IoT end-to-end đủ ổn định để chuyển sang AI. |
| 4 | Phase 3 — Camera và AI baseline | M4 | ESP32-CAM → backend → xử lý ảnh; AI baseline có đánh giá ban đầu. | Có ảnh thật, split dữ liệu, phiên bản model, bảng kết quả và ví dụ lỗi; AI không tham gia quyết định bật bơm an toàn. |
| 5 | Phase 3 — Tích hợp đầy đủ | M5 | Một phiên bản tích hợp IoT, mobile dashboard, camera và AI. | Kiểm tra luồng thật và lỗi xử lý; inference không chặn telemetry/command; đóng phạm vi chức năng. |
| 6 | Phase 4 — Kiểm thử và hardening | M6 | Bản local mobile demo sẵn sàng bảo vệ, có số liệu và bằng chứng; cloud deploy chỉ optional. | Không còn lỗi nghiêm trọng về dừng bơm/điều khiển/luồng dữ liệu; thử kéo dài và nhiều tình huống mạng; nếu làm cloud phải tách khỏi độ tin cậy của demo local. |
| 7 | Phase 5 — Bàn giao | M7 | Repo + báo cáo + slide + video + kịch bản local mobile demo. | Khởi động lại theo README; diễn tập ít nhất hai lượt với smartphone/ESP32; có phương án hotspot dự phòng; giữ vài ngày cuối làm dự phòng. |

## Luồng phụ thuộc chính

G02 → luồng mô phỏng/mobile LAN M1 → phần cứng thật M2 → Manual/Auto và safety M3 → camera/AI M4 → tích hợp M5 → hardening M6 → bàn giao M7.

M1–M3 là đường găng. Không chuyển nguồn lực sang tích hợp AI khi telemetry, command/ACK hoặc giới hạn an toàn của bơm còn lỗi nghiêm trọng. Camera, image API và AI baseline bắt đầu ở tuần 4 sau khi M3 có bằng chứng IoT end-to-end; nếu core trễ thì thu hẹp AI trước, không giảm tiêu chí an toàn. Public Internet deployment không nằm trên đường găng.

## Quy tắc điều chỉnh

- Giữa tuần 2 chưa có core hardware: A đưa phương án mua/mượn/thay linh kiện; cả nhóm cập nhật lịch. M2 không được ghi PASS bằng simulator.
- Cuối tuần 3 chưa có IoT end-to-end ổn định: cả nhóm tiếp tục xử lý core và lùi/thu hẹp AI; ghi rõ ảnh hưởng lịch. Không giảm tiêu chí dừng bơm để chạy kịp.
- Tuần 4 nếu AI thiếu dữ liệu: thu hẹp nhãn hoặc đổi bài toán khả thi; ghi quyết định và cập nhật với thầy nếu thay cam kết. Không gọi HSV là mô hình học máy để thay phần còn thiếu.
- Cuối tuần 5 đóng phạm vi. Weather API không thuộc core scope. Cloud deploy chỉ nhận ở tuần 6 nếu local mobile demo, core IoT và AI baseline đã đạt, có đủ người và thời gian kiểm thử.
- Tuần 6: mục tiêu đề xuất là một phiên theo dõi 4–8 giờ, khoảng 20 lệnh có giám sát, đủ tình huống lỗi quan trọng. Điều chỉnh theo điều kiện thiết bị, ghi đúng số lần và thời gian đã thử.
- Không dùng số liệu dự kiến thay kết quả. Chưa đo lượng nước và đối chứng thì chưa kết luận tiết kiệm nước. Chưa có cảm biến dòng chảy thì trạng thái relay không chứng minh nước đang chảy.

## Tài liệu viết xuyên suốt

Tuần 1: yêu cầu/kiến trúc. Tuần 2: mạch/hiệu chuẩn/schema. Tuần 3: logic tưới/kịch bản lỗi. Tuần 4: dataset/phương pháp AI. Tuần 5: tích hợp/hạn chế. Tuần 6: kết quả. Tuần 7: tổng hợp và diễn tập. Mỗi người bổ sung phần mình thực hiện sau nghiệm thu tuần.
