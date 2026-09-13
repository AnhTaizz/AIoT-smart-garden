# Firmware

Trạng thái: chưa triển khai.

Thư mục này sẽ chứa firmware cho ESP32 và, khi đến phase camera, phần liên quan ESP32-CAM. Trách nhiệm dự kiến:

- Đọc AHT20 và cảm biến độ ẩm đất, báo lỗi cảm biến mà không thay lỗi bằng giá trị `0`.
- Gửi telemetry và nhận command qua MQTT theo contract G02.
- Quản lý trạng thái Manual/Auto, relay/bơm, tưới theo nhịp và hysteresis trên thiết bị.
- Luôn áp dụng giới hạn thời gian chạy bơm và hành vi an toàn khi boot, mất mạng hoặc gặp lỗi.
- Chụp và gửi ảnh khi phạm vi camera được triển khai ở phase sau.

ESP32 là nơi giữ trạng thái tưới và giới hạn an toàn cục bộ. Ngưỡng tưới, thời lượng, chân kết nối và cực kích relay chưa được tự đặt ở bước bootstrap; chúng phải dựa trên G02, BOM và thử nghiệm phần cứng G03.

Không commit SSID, mật khẩu Wi-Fi, chứng thực MQTT hoặc secret thật.

