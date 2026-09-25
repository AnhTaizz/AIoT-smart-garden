# CLAUDE.md

Hướng dẫn này áp dụng cho toàn bộ repository. Đây là dự án đồ án nhóm, vì vậy ưu
tiên thay đổi nhỏ, kiểm chứng được và giữ đúng ranh giới an toàn của hệ thống.

## 1. Đọc trước khi sửa

Đọc các tài liệu liên quan theo thứ tự sau:

1. `README.md` — kiến trúc, cách chạy và phạm vi demo local mobile.
2. `docs/PROJECT_STATE.md` — trạng thái thực tế và các việc còn mở.
3. `docs/INTERFACES.md` — MQTT/API và vòng đời command. File này hiện là
   **DRAFT** cho tới khi G02 được cả nhóm xác nhận.
4. `docs/ROADMAP.md` — dependency và điều kiện nghiệm thu milestone.
5. README của module và file phân công tương ứng trong `docs/assignments/`.

Không tự điền thay nhóm các quyết định G01–G03 như cây trồng, người điều phối,
deadline, pin GPIO, ngưỡng tưới, BOM hoặc xác nhận contract. Có thể đưa ra đề
xuất rõ ràng, nhưng phải giữ trạng thái “chưa chốt” cho tới khi có xác nhận.

## 2. Mục tiêu và kiến trúc

Đích chính là **LOCAL MOBILE DEMO**, không phải public cloud deployment:

```text
ESP32/simulator -> MQTT -> FastAPI -> PostgreSQL -> React -> smartphone
smartphone -> React -> FastAPI -> MQTT command -> ESP32/simulator -> ACK/state
ESP32-CAM -> backend -> image/AI -> backend/frontend                 (phase sau)
```

- Laptop chạy React/Nginx, FastAPI, Mosquitto và PostgreSQL bằng Docker Compose.
- Điện thoại và ESP32 dùng IP LAN của laptop; chúng không dùng hostname Docker.
- Hoàn thiện IoT end-to-end và an toàn bơm trước khi tích hợp AI.
- Weather API, nhiều vùng trồng và public deployment không thuộc core scope.

## 3. Các bất biến không được phá vỡ

### Quyền điều khiển và an toàn

- ESP32 sở hữu trạng thái tưới, Manual/Auto, giới hạn thời gian chạy bơm và hành
  vi an toàn khi boot, mất mạng hoặc sensor lỗi.
- Backend kiểm tra/chuyển lệnh, lưu dữ liệu và cung cấp API; không tạo một bộ
  logic tự tưới thứ hai cạnh tranh với ESP32.
- AI chỉ cung cấp thông tin/cảnh báo, không trực tiếp bật bơm.
- Firmware phải mặc định bơm tắt khi boot, tự dừng theo giới hạn cục bộ và không
  chạy lại lệnh cũ sau reconnect. Không suy đoán pin, cực kích relay hoặc ngưỡng
  an toàn khi BOM/G03 chưa được chốt.

### Vòng đời command

- HTTP `2xx`/`202` chỉ xác nhận backend đã nhận và publish yêu cầu; không có
  nghĩa thiết bị đã thực hiện.
- Giữ cùng `command_id` xuyên suốt request, MQTT command, ACK, state và UI.
- UI và backend phải phân biệt ít nhất `pending`, `applied`, `rejected`,
  `timeout`.
- ACK phải khớp cả `command_id` và `device_id`. ACK tới trễ được ghi nhận nhưng
  không âm thầm đổi `timeout` thành `applied`.
- State là trạng thái thiết bị tự báo; không suy ra relay state từ request gửi đi.
- MQTT command dùng QoS 1 và không retained. Không làm thay đổi này nếu chưa có
  quyết định G02 kèm kiểm thử tương ứng.

### Tính toàn vẹn dữ liệu

- Dữ liệu mô phỏng luôn có `simulated: true`; dữ liệu thiết bị thật dùng
  `simulated: false`. Không trình bày dữ liệu mô phỏng như số đo thật.
- Sensor lỗi dùng `null` cùng trạng thái/lý do phù hợp, không đổi thành số `0`.
- Dùng thời gian ISO 8601 có múi giờ; backend chuẩn hóa UTC khi phát bản tin.
- Validate nghiêm dữ liệu ngoài biên: JSON hỏng, sai kiểu, NaN/Infinity, giá trị
  ngoài miền và `device_id` lệch topic không được lưu như telemetry hợp lệ.
- Không kết luận nước đang chảy chỉ từ trạng thái relay nếu không có bằng chứng
  phần cứng/cảm biến dòng chảy.

### Thay đổi giao tiếp

`docs/INTERFACES.md` là nguồn mô tả contract. Khi thay MQTT topic/payload, REST
API, enum, đơn vị hoặc command lifecycle:

1. Xác định cả producer và consumer bị ảnh hưởng.
2. Sửa code, validation, test và ví dụ tài liệu trong cùng thay đổi.
3. Giữ tương thích nếu có thể; nếu không, ghi rõ migration/breaking change.
4. Không tự đổi trạng thái `DRAFT` thành `AGREED`; cần xác nhận của Thành, Tài và
   Toản theo G02.

## 4. Quy tắc theo module

### Backend (`backend/`)

- Python >= 3.11, FastAPI, Pydantic, psycopg async và paho-mqtt.
- Giữ endpoint async và không thực hiện I/O blocking trong event loop.
- Dùng Pydantic strict validation ở biên MQTT/HTTP; dùng type hint cho code mới.
- SQL phải parameterized. Không ghép dữ liệu người dùng vào câu SQL.
- Giữ `/health` là liveness và `/ready` là PostgreSQL readiness thực sự.
- Lỗi DB/MQTT trả lỗi hữu ích nhưng không lộ credential, DSN hoặc nội dung SQL.
- Migration mới dùng file SQL đánh số tăng dần. Không sửa migration đã được áp
  dụng/chia sẻ trừ khi task nói rõ đây là môi trường có thể tái tạo từ đầu.
- Thay đổi telemetry/command phải có unit test; thay đổi luồng tích hợp phải có
  e2e test với PostgreSQL và MQTT thật khi khả thi.

### Frontend (`frontend/`)

- React + TypeScript strict + Vite; không dùng `any` để né validation API.
- Trình duyệt gọi API qua đường dẫn tương đối `/api` trong cấu hình mặc định.
- Hiển thị rõ loading, empty, stale/offline, error và simulated/real states.
- Không tạo số đo hoặc trạng thái bơm giả để lấp giao diện trống.
- Nút điều khiển chỉ báo thành công sau ACK/state phù hợp, không dựa vào HTTP
  response tạo command.
- Giữ khả năng truy cập cơ bản: semantic element, label/accessible name, trạng
  thái disabled rõ ràng và test theo hành vi người dùng.

### Simulator (`simulator/`)

- Simulator mô phỏng thiết bị qua cùng contract với ESP32, không tạo đường tắt
  gọi thẳng database/backend internals.
- Luôn đánh dấu rõ dữ liệu mô phỏng và giữ hàm tạo payload có thể unit test.
- Khi thêm chiều command, phải mô phỏng ACK/state, timeout/reject, lệnh trùng và
  lệnh hết hạn; không dùng simulator để nghiệm thu M2 phần cứng thật.
- Không chạy simulator và ESP32 thật đồng thời với cùng `device_id` trong phiên
  demo, trừ một test chủ ý được cô lập.

### Firmware (`firmware/`)

- Firmware hiện chưa triển khai. Chỉ chọn framework/toolchain khi task hoặc nhóm
  đã chốt; tài liệu hóa cách build, flash và monitor.
- Tách cấu hình mạng/credential khỏi source được commit.
- Logic dừng bơm phải hoạt động cục bộ kể cả khi Wi-Fi, MQTT hoặc backend mất.
- Xử lý command idempotent; nhận lại cùng `command_id` không kéo dài thời gian
  chạy bơm. Reconnect không được replay một lệnh bật cũ.
- Mọi pin, ADC calibration, relay polarity và giới hạn bơm phải bắt nguồn từ BOM
  và thử nghiệm thật, không dùng giá trị phỏng đoán như mặc định an toàn.

### AI (`ai/`)

- Chỉ bắt đầu tích hợp sau khi core IoT đạt điều kiện roadmap.
- Ghi nguồn/quyền dữ liệu, manifest, quy tắc nhãn và split train/validation/test;
  tránh rò rỉ dữ liệu giữa các split.
- Lưu seed, preprocessing, dependency, metric, dataset version và model version
  để tái hiện kết quả.
- Tách kết quả HSV khỏi kết quả model ML; không gọi HSV là model đã huấn luyện.
- Không commit dataset/model lớn (`.pt`, `.onnx`, `.tflite`, v.v.); ghi vị trí,
  checksum/version và cách lấy artifact.

### Hạ tầng (`compose*.yaml`, `infra/`)

- Development mode mặc định chỉ bind `127.0.0.1`.
- LAN mode chỉ expose frontend và MQTT bằng `compose.lan.yaml`; giữ FastAPI và
  PostgreSQL ở localhost/internal network.
- Cấu hình anonymous MQTT hiện chỉ dành cho mạng/hotspot tin cậy; không dùng cho
  public Internet.
- Không hardcode IP LAN, Wi-Fi, token hoặc mật khẩu. Secret thật chỉ nằm trong
  `.env`/secret store đã bị ignore; `.env.example` chỉ chứa giá trị mẫu.
- Không chạy `docker compose down -v` hoặc xóa named volume nếu người dùng không
  yêu cầu rõ việc xóa dữ liệu.

## 5. Cách làm việc trong repository

- Trước khi sửa, chạy `git status --short` và giữ nguyên thay đổi đang có của
  người dùng. Không reset, checkout hoặc format hàng loạt file ngoài task.
- Chỉ sửa phạm vi cần thiết. Không thêm dependency/framework mới nếu thư viện
  hiện có giải quyết được vấn đề.
- Không tạo dữ liệu, log, ảnh hoặc kết quả test giả để đánh dấu task hoàn thành.
- Không đánh dấu milestone `PASS`, task `Done` hoặc cập nhật
  `PROJECT_STATE.md` như bằng chứng nếu chưa chạy đúng tiêu chí nghiệm thu.
- Khi hành vi/cấu hình/cách chạy thay đổi, cập nhật README hoặc tài liệu liên
  quan trong cùng thay đổi.
- Tên và thông báo hướng người dùng dùng tiếng Việt nhất quán với UI hiện tại;
  identifier/code có thể dùng tiếng Anh rõ nghĩa.
- Không có formatter/linter toàn repo được cấu hình. Theo style của file hiện có
  và tránh reformat không liên quan.

## 6. Kiểm tra tối thiểu

Chạy các kiểm tra liên quan tới phần đã sửa. Không tuyên bố PASS cho lệnh chưa
chạy hoặc test đã bị skip.

### Cấu hình Compose

```bash
docker compose config
docker compose -f compose.yaml -f compose.lan.yaml config
```

### Backend

Từ `backend/`, với dependency development đã cài:

```bash
python -m pytest -v tests/test_validation.py
```

E2E cần stack PostgreSQL/MQTT/API thật; dùng lệnh container và biến môi trường
được mô tả trong `backend/README.md`. Ghi rõ nếu e2e bị skip hoặc không chạy.

### Frontend

Từ `frontend/`:

```bash
npm test
npm run build
```

### Simulator

Từ `simulator/`:

```bash
python -m unittest discover -s tests -v
```

Với thay đổi xuyên module, ngoài test riêng phải chạy một phiên end-to-end theo
checklist M1 trong `docs/ROADMAP.md`: telemetry tới UI và command quay về thiết
bị/simulator qua ACK/state trên cùng `device_id`.

## 7. Tiêu chí hoàn tất thay đổi

Một thay đổi chỉ được coi là hoàn tất khi:

- Đạt tiêu chí task và không phá các bất biến ở trên.
- Có test phù hợp và ghi đúng kết quả/giới hạn.
- Producer/consumer cùng tương thích nếu giao tiếp thay đổi.
- Tài liệu/cấu hình mẫu được cập nhật nếu hành vi vận hành thay đổi.
- Không chứa secret, dữ liệu thật nhạy cảm, dataset/model lớn hoặc artifact build.
- Không phóng đại trạng thái: test thành phần không thay cho bằng chứng end-to-end
  hoặc nghiệm thu phần cứng thật.
