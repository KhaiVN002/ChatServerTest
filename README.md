# metroAsist · Demo baseline LANL

Demo so sánh hoạt động của cùng một máy trong các cửa sổ cùng khung giờ. `POST /chat` chỉ hỗ trợ ba truy vấn điều tra trên mẫu này.

| Tệp gốc | Máy theo dõi | Chỉ số | 7 cửa sổ tham chiếu | Cửa sổ kiểm thử |
|---|---|---|---|---:|
| `auth.txt` | `C706` | Số sự kiện xác thực thất bại tới máy đích | 0, 0, 0, 30, 0, 0, 0 | 164 |
| `flows.txt` | `C5778` | Số máy đích khác nhau trong các flow đi ra | 7, 2, 3, 2, 3, 2, 4 | 14 |
| `proc.txt` | `C19938` | Số mã tiến trình khác nhau có bản ghi `Start` | 8, 3, 5, 6, 5, 4, 8 | 75 |

## Mốc thời gian của mẫu

Các `center` trong `backend/lanl_demo.py` là mốc cố định được chọn bằng tay sau khi xem log để tìm cửa sổ minh họa rõ. Code không tự tính chúng. Đây cũng không phải nhãn sự kiện Red Team. Tài liệu LANL không ghi lý do chọn các mốc cụ thể này. `auth` và `proc` dùng giây `1,174,287`, khoảng 13,6 ngày tính từ đầu dataset. `flows` dùng giây `1,760,026`, khoảng 20,4 ngày. LANL bắt đầu bộ đếm ở giây 1, nên đây là thời gian tương đối, không phải giờ trên lịch. [Tài liệu LANL](https://csr.lanl.gov/data/cyber1/).

## Cách xử lý log

1. `backend/lanl_demo.py` đọc các tệp theo thứ tự thời gian trong `logWin/extracted`. Nó tìm từng đoạn bằng vị trí byte và dừng khi qua mốc cuối. Chỉ các bản ghi của ba máy mẫu được lưu.
2. Mỗi ca có bảy cửa sổ tham chiếu và một cửa sổ kiểm thử. Mỗi cửa sổ lấy các dòng trong ±300 giây quanh mốc giữa. Các mốc tham chiếu cách nhau 86.400 giây. Các giây này tính theo đồng hồ tương đối của LANL.
3. Backend đánh dấu khi giá trị kiểm thử đạt ngưỡng `max(mức tối thiểu, 2 × mức cao nhất trước đó)`. Mức tối thiểu tương ứng là 20, 10 và 10. Ngưỡng dùng cho demo, số liệu chỉ mô tả ba ca được chọn.
4. Mỗi bản ghi giữ nguyên dòng log, nguồn, thời gian và vị trí byte tính từ 0. Mã sự kiện ghép tên nguồn với vị trí byte để nạp lại cùng bộ LANL mà tránh trùng. Câu trả lời đưa tối đa bốn dòng đại diện, trong khi bộ nạp giữ toàn bộ bản ghi của ca mẫu.

## Cách tạo đồ thị

```text
MetroDemo ─HAS_CASE─> MetroCase ─TRACKS─> MetroHost
                          │
                      HAS_WINDOW
                          ▼
                     MetroWindow ─HAS_EVENT─> MetroEvent
                                               ├─ FROM_HOST / TO_HOST ─> MetroHost
                                               ├─ TARGET_ACCOUNT ──────> MetroAccount
                                               └─ OBSERVED_PROCESS ─────> MetroProcess

MetroAccount ─ACTED_IN─> MetroEvent
```

Ví dụ, một flow `C5778 → C585` tạo một nút sự kiện nối hai nút máy và giữ cổng đích `445`. Máy `C5778` được dùng lại cho mọi bản ghi cùng mã máy trong LANL. Sự kiện xác thực có thêm tài khoản, còn sự kiện tiến trình có thêm mã tiến trình. Graph trong giao diện hiển thị các đường đi ứng với những dòng log được trích dẫn.

## Chạy demo

Mở PowerShell tại backend. Dùng môi trường `.venv` có sẵn của project.

```powershell
Set-Location 'D:\Chat Server test\backend'
& '.\.venv\Scripts\python.exe' -B lanl_demo.py --stage baseline
& '.\.venv\Scripts\python.exe' -B -m uvicorn main:app --port 8080
```

Mở PowerShell thứ hai để chạy frontend.

```powershell
Set-Location 'D:\Chat Server test\frontend'
npm run dev -- --port 5173 --strictPort
```

Vào `http://localhost:5173`, hỏi **“Máy nào có số lần xác thực thất bại tăng đột biến?”**. Lúc đầu backend hiện baseline và báo đang chờ cửa sổ kiểm thử. Nạp bước tiếp theo trong PowerShell thứ ba, tại backend, rồi hỏi lại.

```powershell
& '.\.venv\Scripts\python.exe' -B lanl_demo.py --stage replay
```

Ở chế độ cục bộ, backend đọc bản chụp `backend/data/lanl_baseline.json` và nhận dữ liệu mới ở lần hỏi kế tiếp. Bản chụp có thể tái tạo từ log bằng hai lệnh trên.

### Dùng Neo4j làm kho truy vấn

Với Neo4j đang chạy, đặt biến kết nối ở cả cửa sổ chạy bộ nạp và cửa sổ chạy API. `NEO4J_DATABASE` mặc định là `neo4j`. Tài khoản bộ nạp cần quyền tạo ràng buộc và ghi dữ liệu.

```powershell
$env:NEO4J_URI = 'bolt://127.0.0.1:7687'
$env:NEO4J_USER = 'neo4j'
$env:NEO4J_PASSWORD = Read-Host 'Mật khẩu Neo4j' -MaskInput
& '.\.venv\Scripts\python.exe' -B lanl_demo.py --stage baseline --neo4j
```

Khởi động API sau khi đã cấu hình các biến. Đến bước mô phỏng dữ liệu mới, chạy lại bộ nạp với `--stage replay --neo4j`. Mỗi lần import cập nhật các nút bằng mã ổn định trong một giao dịch. Khi chọn baseline, API chỉ đọc bảy cửa sổ tham chiếu. Khi chọn replay, API đọc thêm cửa sổ kiểm thử. [Tài liệu giao dịch của Neo4j](https://neo4j.com/docs/python-manual/current/transactions/)

LANL là dữ liệu lịch sử. Hai bước trên mô phỏng việc nhận log theo lô. Khi nối nguồn log khác, thêm bộ đọc theo định dạng nguồn, giữ mã sự kiện và vị trí đọc, rồi cập nhật các cửa sổ bị ảnh hưởng trước khi đưa kết quả mới cho API.

