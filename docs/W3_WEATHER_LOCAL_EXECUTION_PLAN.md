# Kế hoạch bổ sung W3 — Weather-aware Auto Irrigation và kiểm thử Claude Code local

Ngày lập: 2026-10-31. **Loại:** thay đổi phạm vi theo yêu cầu chủ dự án; **chưa phải bằng chứng G02 AGREED/M3 PASS**. Phạm vi bổ sung nằm trong W3 (M3), không thay mã task B-W1...B-W7 và không thay việc của A/C. A (Thành) và C (Toản) cần xem lại giao tiếp và tiêu chí nghiệm thu.

## 0. Trạng thái nguồn phải kiểm tra lại trước mọi thao tác

Snapshot từ GitHub ngày 2026-10-31:
- `main` = `13e1ac0`; PR #2/#3/#5 đã merge.
- PR #6 BC-01: Draft, chưa merge, head `57f78b6`.
- PR #7 BC-02/BC-02.1: Draft, base = nhánh PR #6, head `1a3db7b`. Báo cáo gần nhất: backend **215 pass, 2 skip** (167 unit + 48 E2E), simulator 31/31, frontend 73/73, build và Capacitor sync OK. Đây là **kết quả do agent báo cáo**, không phải kiểm chứng lại trên máy mới.
- G02 vẫn DRAFT; M1 chưa có bằng chứng nghiệm thu smartphone LAN trong cùng phiên; M2/M3 chưa nghiệm thu.
- APK, Android runtime của phiên BC-02, Cloudflare tunnel thật, Kaggle thật và ESP32 thật chưa được xác minh ở các phiên review này.
- Không đồng nhất kết quả test thành phần với milestone PASS. File `PROJECT_STATE.md` trên `main` cũ hơn branch PR #7.

**Bước đầu tiên trên Claude Code local luôn là AUDIT READ-ONLY**, không sửa file và không tự merge. Đọc `CLAUDE.md`, `docs/PROJECT_STATE.md`, `docs/ROADMAP.md`, `docs/TEAM.md`, `docs/INTERFACES.md`, `docs/assignments/{A-EMBEDDED,B-BACKEND,C-FRONTEND-AI}.md`, BC-01/BC-02_REPORT và PR 6/7; đối chiếu với Git HEAD, nhánh local và upstream trước khi chọn baseline.

### Checklist read-only trên máy local

- `git status --short --branch`, `git branch -vv`, `git log -6 --oneline --decorate`, `git remote -v`, `git fetch origin --prune`, `git status --porcelain=v1`.
- `gh pr view 6` và `gh pr view 7` nếu có GitHub CLI, hoặc đối chiếu qua GitHub. Không auto-merge, auto-rebase, force-push, reset, clean hoặc xóa volume.
- Kiểm tra `docker info`, `docker compose version`, Python/venv, Node/npm, Git/gh, `java -version`, Android SDK/Gradle, `adb devices -l`, cổng 1883/5432/8000/5173, khả năng gọi HTTPS từ laptop. Phân biệt installed / accessible / not tested.
- Chỉ sau khi xác minh baseline và biến môi trường local hợp lệ mới chạy các test. Không in `.env`, password/hash/Bearer token hoặc log chứa secret.
- Báo cáo trước khi sửa: branch/HEAD, PR base, dirty files, test có thể chạy, test cần thiết bị, blocker và task tiếp theo.

## 1. Mục tiêu và phạm vi

Kết hợp **độ ẩm đất thật** với **dự báo mưa** để quyết định **có nên hoãn lần tưới Auto hay không**, đồng thời hiển thị lý do và thông tin dự báo ở dashboard. Dự báo không phải lệnh khởi động bơm và không bảo đảm chắc chắn có mưa.

- Dùng Open-Meteo Forecast API ở backend, không gọi trực tiếp từ firmware, không đưa API URL động do client nhập vào; cấu hình tọa độ vườn qua env.
- Weather advisory chỉ có quyền **hạn chế/hoãn một chu kỳ Auto**, không tự phát lệnh `pump_on` và không thay thế state machine/hysteresis/fail-safe của ESP32.
- ESP32 (A) vẫn quyết định relay và giới hạn bơm; STOP/manual và giới hạn thời gian có mức ưu tiên cao hơn advisory.
- Không sửa sơ đồ topic MQTT G02 hoặc thêm payload A/C phải hiểu trước khi có review G02; contract weather là một **đề xuất mới**, cần A+B+C chốt.
- Cho phép bật/tắt tính năng bằng cờ cấu hình, mặc định **OFF** cho đến khi hợp đồng giao tiếp, tests và phần cứng đạt nghiệm thu; rollback bằng flag không phá tưới local.

## 2. Dữ liệu weather và semantics

Provider đề xuất: https://open-meteo.com/en/docs (non-commercial free usage: https://open-meteo.com/en/terms).

- Input: `WEATHER_LATITUDE`, `WEATHER_LONGITUDE`, timezone `Asia/Ho_Chi_Minh`, khoảng dự báo đề xuất 6 giờ (GET 12 giờ để UI hiển thị tùy chọn), cập nhật cache thưa (đề xuất 30–60 phút).
- Dữ liệu: `hourly.precipitation_probability` (% **mỗi giờ**), `hourly.precipitation` (mm mỗi giờ), `hourly.temperature_2m`; tổng mưa cửa sổ tính bằng cộng các giờ hợp lệ, xác suất đại diện là **max xác suất mưa từng giờ**, không diễn giải thành xác suất ít nhất một trận mưa trong toàn bộ cửa sổ.
- Chuẩn hóa time to UTC, lưu `fetched_at`, `valid_until`, `forecast_window_start/end`, `provider` và source timestamp; kiểm tra thiếu/null/NaN, số lượng time/data mismatch, out-of-range.
- Phân biệt `fresh`, `stale`, `unavailable`, `disabled`. `stale` không được hiển thị như dự báo realtime và **không dùng làm căn cứ mới để hoãn tưới**.
- Provider timeout, 429/5xx, mất Internet, không cấu hình lat/lon: backend không crash; bảo vệ cache và báo nguồn lỗi; không gọi provider liên tục hoặc từ mỗi nhịp telemetry.
- Ngưỡng `rain_probability`, `precipitation_mm`, `forecast_window`, dry/critical soil, timeout advisory chỉ là **đề xuất cần nhóm hiệu chuẩn**; không lấy số ví dụ làm ngưỡng sản xuất.

## 3. Phân vai theo task gốc

### B (Tài)

- **B-W2-01/02:** xác minh telemetry thật, state/command và các chặn an toàn với ESP32 trước khi mở Auto-weather; không nâng M2 PASS nếu chỉ simulator.
- **B-W3-01 — mở rộng**: (a) weather adapter/cache/config + REST read-only có auth + tests; (b) weather advisory `delay/no_delay/unknown` và lý do, tích hợp nhật ký tưới; (c) phối hợp thiết kế weather advisory TTL/sequence với A+C và chỉ code đường MQTT sau khi contract được duyệt.
- **B-W3-02 — mở rộng**: regression mất provider, cache stale, backend restart, MQTT disconnect/reconnect, sai đồng hồ, lệnh bị trễ/trùng, thiếu sensor, rollback flag OFF. Weather không tự gửi ON.
- **B-W4 đến B-W7:** giữ nguyên API ảnh/inference/đo lường/bàn giao của kế hoạch gốc; chỉ bắt đầu khi core an toàn. B-W3-01 giờ lớn hơn 4h dự toán cũ, cần đánh giá lại tổng effort sau audit.

### A (Thành)

- **A-W3-01:** mở rộng state machine Manual/Auto để có khả năng **hoãn** tưới theo advisory fresh/đúng target; không khởi động bơm chỉ vì weather; sensor lỗi/overrun/STOP vẫn ưu tiên tuyệt đối.
- **A-W3-02:** kiểm tra TTL, duplicate, reboot, mất MQTT, nội dung advisory bất hợp lệ và fallback khi weather mất. A phê duyệt topic/payload trước khi B triển khai.

### C (Toản)

- **C-W3-01:** Weather Card, dự báo 6–12h, `fresh/stale/unavailable`, Auto/Manual và giải thích lý do `delay/no_delay/unknown`, không hiển thị forecast như cảm biến tại vườn.
- **C-W3-02:** UI cảnh báo khi data stale/offline, API lỗi, phiên hết hạn, cấu hình chưa được ESP32 ACK, và lỗi AUTO/STOP. C review REST schema ở G02.

## 4. Trình tự triển khai bằng Claude Code trên máy local

**P0 — AUDIT / TRIAGE (chỉ đọc):** xác minh branch/PR/state/scope, công cụ, phần cứng, môi trường và baseline tests. Không sửa repo trong bước audit.

**P1 — TÀI LIỆU & CONTRACT DRAFT:** cập nhật ROADMAP, assignments A/B/C, INTERFACES (phần weather ghi PROPOSED), PROJECT_STATE (quyết định mở rộng còn chờ review A/C). Không tự đánh dấu G02/M1/M3 PASS, không sửa firmware.

**P2 — B-W3-01a (read-only):** FastAPI adapter Open-Meteo + Pydantic validation + timeout/cache/UTC/errors + REST auth (chẳng hạn `GET /devices/{device_id}/weather`, **chưa chốt endpoint**), fixture và test. Không phát MQTT command/weather ở bước này. Tạo commit/PR nhỏ sau regression.

**P3 — B-W3-01b (advisory dry-run):** tính lý do `delay/no_delay/unknown` từ dữ liệu dự báo fresh và soil mới nhất; chỉ lưu/log/hiển thị khuyến nghị, tuyệt đối chưa điều khiển relay. Test bảng quyết định có cả sai forecast, critical dry, thiếu humidity.

**P4 — G02 CROSS-REVIEW + A/C IMPLEMENT:** chốt cấu trúc config/advisory với Thành và Toản (boot/sequence/TTL/expiry, ACK, mode authority, rollback), cập nhật INTERFACES và version; simulator trước firmware; riêng A tích hợp firmware Auto, C tích hợp UI. Chỉ bật weather-aware Auto khi có xác nhận.

**P5 — M3 E2E:** Compose thật (PostgreSQL, MQTT, API, Nginx) + fake weather provider + simulator; kịch bản fresh/mưa, không mưa, outage, stale, reboot, mất MQTT, STOP, sensor fault. Sau đó thử ESP32/relay với giám sát, ưu tiên LED hoặc bơm ngắt tải trước, tránh tưới không giám sát. Smartphone LAN + APK/4G nếu thiết bị/SDK/tunnel thực sự sẵn; log lại chưa test nếu thiếu.

**P6 — BÁO CÁO:** làm rõ kết quả đã chạy thực tế tại máy local, số pass/skip, thiết bị, bằng chứng/ảnh/log đã che secret; không biến passed unit/simulator thành M1/M2/M3 PASS.

## 5. Ma trận hành vi dự kiến (cần A+B+C phê duyệt)

| Sensor / thời tiết | Hành vi đề xuất | Điều kiện |
| --- | --- | --- |
| Đất đủ ẩm | Không tưới | Logic soil local |
| Đất khô, weather fresh, có dấu hiệu mưa đáng kể | Hoãn **chu kỳ Auto**, ghi reason + deadline | Không vô hiệu STOP |
| Đất khô, weather fresh, ít/không mưa | Chỉ cho phép state machine Auto local tự xét tưới | Weather không kích ON |
| Đất rất khô | Theo chính sách critical dry được hiệu chuẩn, không dựa duy nhất forecast | Hysteresis, thời lượng và safety luôn áp dụng |
| Dự báo stale/unavailable/không có Internet | Bỏ ảnh hưởng weather, dùng policy soil local an toàn đã được phê duyệt | Không dùng forecast cũ để giữ HOLD mãi |
| Soil sensor lỗi | Khóa tự kích ON, cảnh báo | Không coi 0 là độ ẩm thật |
| MQTT mất/reconnect, clock/boot sai | Không áp dụng advisory sai/đã hết hạn; giữ thiết bị an toàn | Không replay ON cũ |

**Giá trị ngưỡng** (xác suất mưa, lượng mưa, ẩm đất, số phút hoãn) phải được hiệu chuẩn trên dữ liệu thật, không sử dụng ví dụ 70%/2 mm như default cứng.

## 6. Chính sách kiểm thử local

- **Backend:** pytest unit; E2E dùng PostgreSQL + Mosquitto + FastAPI + Nginx thực; fake upstream HTTP cho weather; test malformed JSON, 429, 5xx, timeout, timezone, cache, TTL, auth 401/403.
- **Simulator/Firmware:** test G02 command/ACK/state, STOP, no replay ON, fail-safe; dùng relay LED/dry-run và xác nhận Thành trước khi cấp nguồn bơm thật.
- **Frontend:** Vitest + TypeScript/Vite build + Chromium responsive; Android Gradle APK và `adb`/thiết bị vật lý nếu local có SDK.
- **Live weather smoke:** chỉ chạy thêm sau test determinisitic, kết quả mạng/provider hiện thời không là dependency của CI; không giả định provider luôn sẵn.
- **Security:** token/auth nằm server; không thêm secret frontend; không expose MQTT/DB; tránh SSRF qua URL tùy ý; có timeout và cache; kiểm tra license attribution Open-Meteo cho demo.
- **Trạng thái:** ghi PASS / FAIL / SKIP / NOT RUN riêng cho unit/E2E/Android/ESP32/4G; không bịa bằng chứng.

## 7. Quản lý nhánh và phạm vi

Không commit hoặc cherry-pick chồng mã BC-01/BC-02. Vì PR #6/#7 còn Draft và stacked, việc sửa code sau này phải dựa trên HEAD đã kiểm tra thực tế. Không đổi base/merge PR #6/#7 khi chưa có review. Tạo PR nhỏ, chỉ một mục tiêu, tách kế hoạch khỏi implementation. Không thay trạng thái G02 DRAFT hay M1 chưa nghiệm thu nếu thiếu bằng chứng cả nhóm.

## 8. Acceptance cho mở rộng M3

- Contract G02 weather/mode có xác nhận từ A+B+C.
- Dữ liệu weather có nguồn, thời hạn hiệu lực, lỗi rõ ràng; có thể tắt hoàn toàn bằng feature flag.
- Firmware vẫn chịu trách nhiệm relay; weather chỉ hoãn, không kích ON.
- Các lỗi API/mạng/sensor/boot/reconnect/STOP không phá giới hạn bơm.
- UI hiện phân biệt advisory, forecast và state vật lý; có lý do tưới hoặc hoãn tưới.
- E2E simulator PASS và phiên firmware/relay được quan sát theo checklist trước khi đánh dấu M3 PASS.
