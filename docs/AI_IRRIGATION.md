# Điều phối tưới AI — thử nghiệm simulator

Backend tự đánh giá theo chu kỳ, không cần mở chat: đọc telemetry/state và lịch sử → gọi AI → validate quyết định JSON → kiểm tra điều kiện → dự trù ngân sách → gửi command MQTT → theo dõi ACK/state.

**Bản này chỉ cho phép simulator.** Telemetry `simulated=false` bị chặn trong code. [Firmware Arduino IDE](../firmware/README.md) đã có, nhưng chưa nghiệm thu tích hợp trên board thật, hiệu chuẩn cảm biến và lưu lượng bơm. AUTO là chế độ điều phối backend; thiết bị vẫn báo mode MANUAL và giữ timer cục bộ. Thiết bị có AUTO riêng bị chặn để tránh hai bộ quyết định cạnh tranh.

## Cách dùng

1. Chạy `docker compose up --build -d` để build và áp dụng migration.
2. Nếu không có ESP32 nào đang dùng `node_01`, chạy `.\.venv\Scripts\python.exe simulator/simulator.py --device-id node_01 --interval 2`.
3. Điền bảng **Điều phối tưới AI** trên dashboard: cây, giai đoạn, giá thể, giới hạn ẩm ngừng tưới, nhịp tưới tối đa, thời gian nghỉ, ngân sách AUTO/24 giờ và chu kỳ đánh giá.
4. Ví dụ chỉ cho phần mềm mô phỏng: ghi cây/giai đoạn/giá thể là mô phỏng; ngừng từ 80%, nhịp 2 giây, nghỉ 300 giây, ngân sách 10 giây/24h, đánh giá mỗi 60 giây. Đây không phải cấu hình khuyến nghị cho cây thật.
5. Bật AUTO, xem lịch sử quyết định và command/relay xác nhận. Dùng MANUAL/STOP để hủy điều phối và yêu cầu dừng.

## Quy tắc

- AI phải trả `{"water":true,"duration_seconds":1,"reason":"Lý do"}` hoặc `{"water":false,"duration_seconds":0,"reason":"Lý do"}`. Không chuyển lời văn chat thành lệnh; không có thuật toán ngưỡng thay AI khi model lỗi.
- Chỉ chạy khi cảm biến OK, dữ liệu mới, clock đồng bộ, boot khớp và relay OFF. Kiểm tra lại sau khi AI trả lời; số đo AI dùng đã hết hạn thì bỏ quyết định.
- Giới hạn ẩm là quyền phủ quyết. Nghỉ tối thiểu 300 giây, nhịp tối đa 60 giây và chịu thêm giới hạn command/thiết bị, ngân sách AUTO tối đa 600 giây trong cửa sổ 24 giờ.
- Dự trù thời lượng và mốc nghỉ được commit trước publish; lỗi gửi vẫn tiêu ngân sách, không tự phát lại ON. Lệnh pending/timeout/rejected chặn lần tiếp; lỗi AI/API/thực thi tắt AUTO.
- Lệnh tay ON/OFF đều tắt AUTO và tăng revision. MANUAL từ bảng cấu hình cũng gửi STOP. Không suy ra bơm đã dừng chỉ từ HTTP; phải đọc ACK/state. Nếu MQTT down, việc dừng phụ thuộc giới hạn thiết bị.
- Backend restart yêu cầu bật AUTO lại. Khóa thiết bị tuần tự hóa thao tác tay và AUTO; lease DB chống hai worker đánh giá/gửi cùng lượt. Khởi động worker mới có thể hủy AUTO đang chạy; demo dùng một backend worker.
- Chatbot `/chat` tiếp tục chỉ tư vấn. Prompt quyết định riêng là `irrigation-decision-v1`. Chưa coi checkpoint Kaggle là đạt chất lượng tưới chỉ vì HTTP 200.

## API và dữ liệu

`GET /devices/{id}/irrigation` trả profile và 20 quyết định gần nhất, gồm command status/ACK/relay xác nhận; `execution_scope=simulator_only`. `PUT` cùng đường dẫn nhận `{enabled, policy}`. Bật yêu cầu dữ liệu simulator hợp lệ. Tắt lưu chế độ trước rồi yêu cầu STOP.

Migration `004_irrigation.sql` thêm profile/lease và nhật ký quyết định. Nhật ký lưu snapshot, policy, prompt version, phản hồi model tối đa 4.000 ký tự, đề xuất, lý do chặn, ngân sách và command ID. `sent` không có nghĩa `applied`; ACK cũng không chứng minh có nước chảy. Ngân sách chỉ tính AUTO; ON bằng tay vẫn cập nhật mốc nghỉ nếu đã có profile.

MQTT command/ACK/state giữ nguyên contract. Không có thay đổi GPIO hay firmware thực. Thông số cây thật phải được hiệu chuẩn và kiểm tra trước khi mở quyền thực thi phần cứng ở phiên bản sau.

## Kiểm thử

Kết quả 2026-11-01: backend unit 109/109, frontend 20/20 và build thành công; E2E 41/41 với PostgreSQL/MQTT thật (33 ca cũ và 8 ca supervisor). Ca AUTO xác nhận ON → ACK/state, không tưới, JSON sai, cooldown, vượt giới hạn, STOP trong lúc chờ AI, timeout lệnh và lease hết hạn. Model trong các ca supervisor là giả lập có kiểm soát. Kiểm tra trực tiếp API Kaggle hiện nhận lỗi HTTP; chưa xác minh quyết định từ Qwen thật ở phiên này. AUTO vẫn tắt mặc định.

Từ `backend/`: `python -m pytest -q tests/test_irrigation.py tests/test_chat.py tests/test_validation.py`.

Từ root, khi Compose đang chạy: `python backend/tests/run_e2e.py -k supervisor`. Các ca supervisor dùng phản hồi AI giả định có nhãn rõ, với PostgreSQL/MQTT/ACK thật; đây là kiểm thử luồng, không phải metric Qwen hay nghiệm thu bơm thật. Nếu Kaggle không trả JSON hợp lệ, hệ thống không gửi ON và tắt AUTO; cần sửa/đánh giá inference rồi chủ động bật lại.
