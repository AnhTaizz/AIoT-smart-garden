# Kế hoạch 7 tuần

Tuần là số tương đối từ ngày nhóm bắt đầu, chưa gán ngày lịch. Ước lượng 10–12 giờ/người/tuần, chỉ lên task chính khoảng 6–8 giờ. Tích hợp mỗi 2–3 ngày; nghiệm thu vào cuối tuần.

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
| 1 | Phase 1 — Nền tảng | M1 | Simulator → MQTT → DB → UI và lệnh ngược lại có phản hồi. | G01–G03 được chốt; một máy khác có thể chạy phần mềm theo hướng dẫn. |
| 2 | Phase 2 — IoT cốt lõi | M2 | Cảm biến thật → dashboard; lệnh từ web → relay/bơm có giới hạn. | Lưu hiệu chuẩn; kiểm tra bơm khởi động tắt và tự dừng; ghi log tích hợp thật. |
| 3 | Phase 2 — IoT cốt lõi | M3 | Manual/Auto, tưới theo nhịp, giới hạn chạy và xử lý lỗi cơ bản. | Đất khô/ẩm, lỗi cảm biến, mất mạng và lệnh trùng được thử; camera gửi được ảnh thử; chốt tính khả thi ML. |
| 4 | Phase 3 — Nâng cao | M4 | Ảnh → backend → xử lý; mô hình baseline có đánh giá ban đầu. | Có split dữ liệu, phiên bản model, bảng kết quả và ví dụ lỗi; chưa tuyên bố hiệu quả trên thực địa từ test công khai. |
| 5 | Phase 3 — Nâng cao | M5 | Một phiên bản tích hợp IoT, dashboard, camera và ML. | Kiểm tra ảnh thật và lỗi xử lý; luồng điều khiển không bị chặn bởi inference; đóng phạm vi chức năng. |
| 6 | Phase 4 — Kiểm thử | M6 | Bản sẵn sàng bảo vệ với số liệu và bằng chứng. | Không còn lỗi nghiêm trọng về dừng bơm/điều khiển/luồng dữ liệu; ghi kết quả thử kéo dài và hạn chế. |
| 7 | Phase 5 — Bàn giao | M7 | Mô hình + repo + báo cáo + slide + video. | Khởi động lại theo README; diễn tập ít nhất hai lượt; giữ vài ngày cuối làm dự phòng. |

## Luồng phụ thuộc chính

G02 → luồng mô phỏng M1 → phần cứng thật M2 → tưới tự động M3 → tích hợp M5 → đánh giá M6 → bàn giao M7.

Chuẩn bị AI chạy song song: C-W1-02 khảo sát dữ liệu → C-W2-02 chuẩn bị dataset → C-W3-02 chốt split/nhãn và thử pipeline → C-W4-01 baseline. Camera: A-W3-02 → A-W4-01; image API: B-W4-01; phục vụ mô hình: B-W5-01. Một nhóm công việc chỉ bắt đầu phần tích hợp khi đầu ra phụ thuộc đã có; có thể tạo khung bằng dữ liệu mẫu trước.

## Quy tắc điều chỉnh

- Giữa tuần 2 chưa có core hardware: A đưa phương án mua/mượn/thay linh kiện; cả nhóm cập nhật lịch. M2 không được ghi PASS bằng simulator.
- Cuối tuần 3 chưa có MVP: ưu tiên cả nhóm xử lý core, bỏ việc mở rộng; ghi rõ ảnh hưởng lịch AI và báo cáo. Không giảm tiêu chí dừng bơm để chạy kịp.
- Cuối tuần 3 AI thiếu dữ liệu: thu hẹp nhãn hoặc đổi bài toán khả thi; ghi quyết định và cập nhật với thầy nếu thay cam kết. Không gọi HSV là mô hình học máy để thay phần còn thiếu.
- Cuối tuần 5 đóng phạm vi. Weather API chỉ nhận nếu core và AI đã đạt, có đủ người và thời gian kiểm thử; mặc định để hướng phát triển.
- Tuần 6: mục tiêu đề xuất là một phiên theo dõi 4–8 giờ, khoảng 20 lệnh có giám sát, đủ tình huống lỗi quan trọng. Điều chỉnh theo điều kiện thiết bị, ghi đúng số lần và thời gian đã thử.
- Không dùng số liệu dự kiến thay kết quả. Chưa đo lượng nước và đối chứng thì chưa kết luận tiết kiệm nước. Chưa có cảm biến dòng chảy thì trạng thái relay không chứng minh nước đang chảy.

## Tài liệu viết xuyên suốt

Tuần 1: yêu cầu/kiến trúc. Tuần 2: mạch/hiệu chuẩn/schema. Tuần 3: logic tưới/kịch bản lỗi. Tuần 4: dataset/phương pháp AI. Tuần 5: tích hợp/hạn chế. Tuần 6: kết quả. Tuần 7: tổng hợp và diễn tập. Mỗi người bổ sung phần mình thực hiện sau nghiệm thu tuần.
