# Quy trình làm việc và đưa lên GitHub

## 1. Tổ chức repo

Bộ này cung cấp tài liệu kế hoạch. Khi triển khai, tạo các thư mục mã nguồn khi thực sự có nội dung: firmware/, simulator/, backend/, frontend/, ai/, infra/. Giữ docs/ cho tài liệu. Không cần tạo hàng loạt file rỗng để thể hiện tiến độ.

## 2. Chuẩn bị repository

Cần xác nhận URL repo đích trước khi push. Nếu chưa có repo, nhóm tạo một repository theo quyền sở hữu và chế độ hiển thị mong muốn, rồi cung cấp URL. Không tự chọn repo khác đang dùng cho môn khác.

Repo mới, chưa có README: đặt bộ file tại gốc. Repo có sẵn: kiểm tra AGENTS.md và tài liệu đang có, tạo nhánh docs/team-plan, ghép nội dung phù hợp; giữ README hiện có và thêm liên kết tới kế hoạch nếu cần.

Các lệnh tham khảo sau chạy sau khi đã thay đường dẫn/URL đúng. Không chạy push nếu chưa kiểm tra đích. Không force push.

```bash
git clone <REPO_URL>
cd <REPO_FOLDER>
git switch -c docs/team-plan
```

Sao chép/ghép bộ tài liệu vào repo, gồm cả thư mục .github. Sau đó:

```bash
git status --short
git diff --stat
git diff
```

Kiểm tra nội dung và chỉ stage các file của thay đổi này:

```bash
git add README.md docs .github
git diff --cached --stat
git diff --cached
git commit -m "docs: add seven-week team plan and assignments"
git push -u origin docs/team-plan
```

Nếu docs/.github đã có thay đổi khác, dùng đường dẫn từng file thay vì stage cả thư mục. Mở PR vào nhánh mặc định thực tế của repo; một bạn khác review trước khi merge. Nhánh mặc định cần luôn chạy được khi đã có ứng dụng.

## 3. Quản lý task trên GitHub

- Tạo milestone W1–W7 theo ROADMAP; điền hạn sau khi chốt ngày bắt đầu. Chưa có ngày thì giữ lịch tuần tương đối.
- Bảng Project: Backlog → Ready → Doing → Review/Test → Done. Blocked là nhãn/field bổ sung, kèm lý do và người cần hỗ trợ.
- Trước mắt tạo Issues G01–G03 và 6 task cá nhân tuần 1. Task tuần sau nằm trong file phân công, được chuyển thành Issues khi lập kế hoạch tuần; không cần tạo 45 issues ngay.
- Tiêu đề giữ mã: `[A-W1-01] Dựng simulator telemetry`. Owner là người làm; Reviewer là người kiểm tra; điền username đã xác nhận, không gán theo suy đoán.
- Nội dung issue lấy từ file cá nhân và mẫu `.github/ISSUE_TEMPLATE/task.md`. Gắn milestone, dependency, giờ dự kiến và tiêu chí nghiệm thu.
- Trước khi có issue, trạng thái nằm trong file cá nhân. Khi có issue, bổ sung link và dùng Issue/Project làm nguồn trạng thái; file giữ kế hoạch/phạm vi. PROJECT_STATE chỉ tóm tắt mốc chung.
- Mỗi người có tối đa một task chính Doing. Task trên 4 giờ tách thành issue con; không coi ước lượng là giới hạn bắt buộc phải code xong.

## 4. Nhánh, review và Done

Mỗi task dùng nhánh ngắn, ví dụ feat/A-W1-01-simulator. PR nhỏ, ghi mục đích, thay đổi, cách chạy và kết quả thử. Mẫu PR có sẵn trong .github.

Task Done khi: đạt tiêu chí đã chốt; có bằng chứng; người khác kiểm tra; tích hợp không làm hỏng luồng đang có; tài liệu liên quan được cập nhật; PR đã merge hoặc đầu ra phi mã nguồn được chấp nhận. Không đánh dấu Done chỉ vì đã mở PR.

Thay MQTT/API cần A/B/C liên quan cùng xem. Không merge thay đổi giao tiếp một phía. Dữ liệu mô phỏng phải được phân biệt với số liệu đo thật. Không commit mật khẩu, token, Wi-Fi thật, thư mục môi trường, model/dataset lớn vào Git thông thường; ghi đường dẫn, phiên bản và cách lấy artifact theo thỏa thuận nhóm.

## 5. Nhịp phối hợp

Đầu tuần 30 phút: chốt một mục tiêu demo, lấy task vừa sức, kiểm tra phụ thuộc và giờ rảnh. Mỗi ngày cập nhật ngắn đã xong/tiếp theo/đang vướng. Mỗi 2–3 ngày chạy luồng chung. Cuối tuần 45–60 phút nghiệm thu theo mẫu WEEKLY_REVIEW.

Vướng quá một buổi: báo lỗi và cách đã thử. Trễ task: ưu tiên hỗ trợ điểm chặn, tách việc, bỏ phần mở rộng; ghi ảnh hưởng trong PROJECT_STATE. Không chuyển milestone sang PASS khi chưa đủ điều kiện. Sau tuần 5 ưu tiên lỗi và chất lượng, hạn chế nhận chức năng mới.

## 6. Bằng chứng tối thiểu

Mỗi task có commit/PR hoặc artifact; một cách tái hiện; log/ảnh/video phù hợp; kết quả và giới hạn. Không cần kiểm thử tự động cho mọi sửa tài liệu/UI nhỏ; ưu tiên kiểm tra có ý nghĩa cho command, timeout, sensor lỗi, dữ liệu, ML và tích hợp.
