# 自作PCパーツ構成・価格監視

更新: 2026-10-14T20:03:59+09:00
予算: PC本体 ¥330,200 / 周辺機器 ¥69,800 / 総額 ¥400,000

**購入方式:** 自作PCを正式な本命として最適化します。組み立て時間・作業時間は減点しません。BTOは同等仕様での総額・部品品質・保証のベンチマークとして比較し、便利さだけを理由に自作から切り替えません。

**注意:** BF購入目標は購入希望額です。比較サイト価格は市場参考値であり、店舗の決済価格・在庫・公式BF実売価格ではありません。現在のデータから購入許可は出しません。

|順位|構成|部品目標小計|PC本体目標総額|周辺機器込み目標|目標残額|比較参考合計|互換性|判定|
|---:|---|---:|---:|---:|---:|---:|---|---|
|1|自作本命：Ryzen 7 9700X + RTX 5070 12GB|¥311,360|¥320,360|¥390,160|¥9,840|未確認|PASS|WAIT_FOR_MARKET_REFERENCE|
|2|自作VRAM案：Ryzen 7 9700X + RTX 5060 Ti 16GB|¥286,360|¥295,360|¥365,160|¥34,840|未確認|REVIEW|WAIT_FOR_COMPATIBILITY_REVIEW|
|3|自作大穴：Ryzen 7 9700X + RTX 5070 Ti 16GB|¥320,360|¥329,360|¥399,160|¥840|未確認|REVIEW|WAIT_FOR_COMPATIBILITY_REVIEW|

## 自作本命：Ryzen 7 9700X + RTX 5070 12GB

- PC本体目標（送料・小物予備費込み）: ¥320,360
- 周辺機器込み目標: ¥390,160 / 残額 ¥9,840
- 現在の比較参考合計: 未算出。部品価格の欠落・不一致・古さを0円補完しない
- 互換性: PASS / 判定: WAIT_FOR_MARKET_REFERENCE

|部品|型番|BF目標|検証済み/表示専用参考値|直接掲載価格（在庫条件未達・推定不採用）|確認状態|リンク|
|---|---|---:|---:|---|---|---|
|AMD Ryzen 7 9700X BOX|100-100001404WOF|¥38,000|¥67,890（検索スニペット参考のみ）|—|search_snippet_reference_only|[価格比較ページ](https://kakaku.com/item/K0001630332/) / [検索ページ参考元](https://search.kakaku.com/AMD%20Ryzen%207%209700X%20BOX/)|
|ASRock B850M Pro RS WiFi|B850M Pro RS WiFi|¥20,000|¥23,780（検索スニペット参考のみ）|¥21,380（取寄せ/予約）|search_snippet_reference_only|[価格比較ページ](https://kakaku.com/item/K0001669878/) / [直接掲載ページ](https://www.ark-pc.co.jp/i/12201558/) / [検索ページ参考元](https://search.kakaku.com/ASRock%20B850M%20Pro%20RS%20WiFi/)|
|TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)|CTCWD532G6000HC38ADC01|¥40,000|未取得|—|missing|[価格比較ページ](https://kakaku.com/item/K0001610896/)|
|Crucial P3 Plus CT1000P3PSSD8JP 1TB|CT1000P3PSSD8JP|¥18,000|¥33,600（検索スニペット参考のみ）|—|search_snippet_reference_only|[価格比較ページ](https://kakaku.com/item/K0001466997/) / [検索ページ参考元](https://search.kakaku.com/Crucial%20P3%20Plus%20CT1000P3PSSD8JP%201TB/)|
|Corsair RM850e 2025 850W ATX 3.1 Gold|CP-9020296-JP|¥14,000|¥17,580（検索スニペット参考のみ）|—|search_snippet_reference_only|[価格比較ページ](https://kakaku.com/item/K0001671441/) / [検索ページ参考元](https://search.kakaku.com/Corsair%20RM850e%202025%20850W%20ATX%203.1%20Gold/)|
|Fractal Design Pop Air TG|FD-C-POA1A-02|¥12,000|¥13,311（検索スニペット参考のみ）|—|search_snippet_reference_only|[価格比較ページ](https://kakaku.com/item/J0000039064/) / [検索ページ参考元](https://search.kakaku.com/Fractal%20Design%20Pop%20Air%20TG/)|
|Thermalright Peerless Assassin 120 SE V3|Peerless Assassin 120 SE V3|¥5,000|¥4,980（検索スニペット参考のみ）|—|search_snippet_reference_only|[価格比較ページ](https://kakaku.com/item/K0001789043/) / [検索ページ参考元](https://search.kakaku.com/Thermalright%20Peerless%20Assassin%20120%20SE%20V3/)|
|Windows 11 Home official retail license reference|Windows 11 Home|¥19,360|¥19,360|—|manual_official_store_reference|[価格比較ページ](https://www.microsoft.com/ja-jp/d/windows-11-home/dg7gmgf0krt0)|
|PNY GeForce RTX 5070 12GB OC SLIM|VCG507012DFXPB1-O|¥145,000|¥190,800（検索スニペット参考のみ）|—|search_snippet_reference_only|[価格比較ページ](https://kakaku.com/item/K0001798041/) / [検索ページ参考元](https://search.kakaku.com/PNY%20GeForce%20RTX%205070%2012GB%20OC%20SLIM/)|

互換性チェック:

- **PASS**: cpu_motherboard_socket — CPU socket AM5 / board socket AM5
- **PASS**: memory_type_capacity_dual_channel — DDR type, >= 32GB, >= 2 DIMMs
- **PASS**: storage_capacity_interface — NVMe SSD 1000GB / minimum 1000GB
- **PASS**: motherboard_case_form_factor — Board MicroATX / case supports ATX, MicroATX, MiniITX
- **PASS**: gpu_case_clearance — GPU 290mm / case limit 405mm
- **PASS**: cooler_socket — AM5 mounting support declared
- **PASS**: cooler_case_clearance — Cooler 157mm / case limit 170mm
- **PASS**: psu_wattage — PSU 850W / GPU recommendation 650W
- **PASS**: gpu_power_connector — PSU ATX 3.1 native 12V-2x6 cable
- **PASS**: os_license — Windows 11 Home license budgeted unless an existing transferable license is confirmed

## 自作VRAM案：Ryzen 7 9700X + RTX 5060 Ti 16GB

- PC本体目標（送料・小物予備費込み）: ¥295,360
- 周辺機器込み目標: ¥365,160 / 残額 ¥34,840
- 現在の比較参考合計: 未算出。部品価格の欠落・不一致・古さを0円補完しない
- 互換性: REVIEW / 判定: WAIT_FOR_COMPATIBILITY_REVIEW

|部品|型番|BF目標|検証済み/表示専用参考値|直接掲載価格（在庫条件未達・推定不採用）|確認状態|リンク|
|---|---|---:|---:|---|---|---|
|AMD Ryzen 7 9700X BOX|100-100001404WOF|¥38,000|¥67,890（検索スニペット参考のみ）|—|search_snippet_reference_only|[価格比較ページ](https://kakaku.com/item/K0001630332/) / [検索ページ参考元](https://search.kakaku.com/AMD%20Ryzen%207%209700X%20BOX/)|
|ASRock B850M Pro RS WiFi|B850M Pro RS WiFi|¥20,000|¥23,780（検索スニペット参考のみ）|¥21,380（取寄せ/予約）|search_snippet_reference_only|[価格比較ページ](https://kakaku.com/item/K0001669878/) / [直接掲載ページ](https://www.ark-pc.co.jp/i/12201558/) / [検索ページ参考元](https://search.kakaku.com/ASRock%20B850M%20Pro%20RS%20WiFi/)|
|TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)|CTCWD532G6000HC38ADC01|¥40,000|未取得|—|missing|[価格比較ページ](https://kakaku.com/item/K0001610896/)|
|Crucial P3 Plus CT1000P3PSSD8JP 1TB|CT1000P3PSSD8JP|¥18,000|¥33,600（検索スニペット参考のみ）|—|search_snippet_reference_only|[価格比較ページ](https://kakaku.com/item/K0001466997/) / [検索ページ参考元](https://search.kakaku.com/Crucial%20P3%20Plus%20CT1000P3PSSD8JP%201TB/)|
|Corsair RM850e 2025 850W ATX 3.1 Gold|CP-9020296-JP|¥14,000|¥17,580（検索スニペット参考のみ）|—|search_snippet_reference_only|[価格比較ページ](https://kakaku.com/item/K0001671441/) / [検索ページ参考元](https://search.kakaku.com/Corsair%20RM850e%202025%20850W%20ATX%203.1%20Gold/)|
|Fractal Design Pop Air TG|FD-C-POA1A-02|¥12,000|¥13,311（検索スニペット参考のみ）|—|search_snippet_reference_only|[価格比較ページ](https://kakaku.com/item/J0000039064/) / [検索ページ参考元](https://search.kakaku.com/Fractal%20Design%20Pop%20Air%20TG/)|
|Thermalright Peerless Assassin 120 SE V3|Peerless Assassin 120 SE V3|¥5,000|¥4,980（検索スニペット参考のみ）|—|search_snippet_reference_only|[価格比較ページ](https://kakaku.com/item/K0001789043/) / [検索ページ参考元](https://search.kakaku.com/Thermalright%20Peerless%20Assassin%20120%20SE%20V3/)|
|Windows 11 Home official retail license reference|Windows 11 Home|¥19,360|¥19,360|—|manual_official_store_reference|[価格比較ページ](https://www.microsoft.com/ja-jp/d/windows-11-home/dg7gmgf0krt0)|
|PNY GeForce RTX 5060 Ti 16GB OC|VCG5060T16DFXPB1-O|¥120,000|¥134,800（検索スニペット参考のみ）|—|search_snippet_reference_only|[価格比較ページ](https://kakaku.com/item/K0001696163/) / [検索ページ参考元](https://search.kakaku.com/PNY%20GeForce%20RTX%205060%20Ti%2016GB%20OC/)|

互換性チェック:

- **PASS**: cpu_motherboard_socket — CPU socket AM5 / board socket AM5
- **PASS**: memory_type_capacity_dual_channel — DDR type, >= 32GB, >= 2 DIMMs
- **PASS**: storage_capacity_interface — NVMe SSD 1000GB / minimum 1000GB
- **PASS**: motherboard_case_form_factor — Board MicroATX / case supports ATX, MicroATX, MiniITX
- **REVIEW**: gpu_case_clearance — Exact GPU retail-card length or case clearance must be verified before ordering
- **PASS**: cooler_socket — AM5 mounting support declared
- **PASS**: cooler_case_clearance — Cooler 157mm / case limit 170mm
- **PASS**: psu_wattage — PSU 850W / GPU recommendation 650W
- **REVIEW**: gpu_power_connector — Confirm exact GPU auxiliary connector and included PSU cable against the exact model
- **PASS**: os_license — Windows 11 Home license budgeted unless an existing transferable license is confirmed

## 自作大穴：Ryzen 7 9700X + RTX 5070 Ti 16GB

- PC本体目標（送料・小物予備費込み）: ¥329,360
- 周辺機器込み目標: ¥399,160 / 残額 ¥840
- 現在の比較参考合計: 未算出。部品価格の欠落・不一致・古さを0円補完しない
- 互換性: REVIEW / 判定: WAIT_FOR_COMPATIBILITY_REVIEW

|部品|型番|BF目標|検証済み/表示専用参考値|直接掲載価格（在庫条件未達・推定不採用）|確認状態|リンク|
|---|---|---:|---:|---|---|---|
|AMD Ryzen 7 9700X BOX|100-100001404WOF|¥38,000|¥67,890（検索スニペット参考のみ）|—|search_snippet_reference_only|[価格比較ページ](https://kakaku.com/item/K0001630332/) / [検索ページ参考元](https://search.kakaku.com/AMD%20Ryzen%207%209700X%20BOX/)|
|ASRock B850M Pro RS WiFi|B850M Pro RS WiFi|¥20,000|¥23,780（検索スニペット参考のみ）|¥21,380（取寄せ/予約）|search_snippet_reference_only|[価格比較ページ](https://kakaku.com/item/K0001669878/) / [直接掲載ページ](https://www.ark-pc.co.jp/i/12201558/) / [検索ページ参考元](https://search.kakaku.com/ASRock%20B850M%20Pro%20RS%20WiFi/)|
|TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)|CTCWD532G6000HC38ADC01|¥40,000|未取得|—|missing|[価格比較ページ](https://kakaku.com/item/K0001610896/)|
|Crucial P3 Plus CT1000P3PSSD8JP 1TB|CT1000P3PSSD8JP|¥18,000|¥33,600（検索スニペット参考のみ）|—|search_snippet_reference_only|[価格比較ページ](https://kakaku.com/item/K0001466997/) / [検索ページ参考元](https://search.kakaku.com/Crucial%20P3%20Plus%20CT1000P3PSSD8JP%201TB/)|
|Corsair RM850e 2025 850W ATX 3.1 Gold|CP-9020296-JP|¥14,000|¥17,580（検索スニペット参考のみ）|—|search_snippet_reference_only|[価格比較ページ](https://kakaku.com/item/K0001671441/) / [検索ページ参考元](https://search.kakaku.com/Corsair%20RM850e%202025%20850W%20ATX%203.1%20Gold/)|
|Fractal Design Pop Air TG|FD-C-POA1A-02|¥12,000|¥13,311（検索スニペット参考のみ）|—|search_snippet_reference_only|[価格比較ページ](https://kakaku.com/item/J0000039064/) / [検索ページ参考元](https://search.kakaku.com/Fractal%20Design%20Pop%20Air%20TG/)|
|Thermalright Peerless Assassin 120 SE V3|Peerless Assassin 120 SE V3|¥5,000|¥4,980（検索スニペット参考のみ）|—|search_snippet_reference_only|[価格比較ページ](https://kakaku.com/item/K0001789043/) / [検索ページ参考元](https://search.kakaku.com/Thermalright%20Peerless%20Assassin%20120%20SE%20V3/)|
|Windows 11 Home official retail license reference|Windows 11 Home|¥19,360|¥19,360|—|manual_official_store_reference|[価格比較ページ](https://www.microsoft.com/ja-jp/d/windows-11-home/dg7gmgf0krt0)|
|PNY GeForce RTX 5070 Ti 16GB ARGB|VCG5070T16TFXPB1-O|¥154,000|¥428,800（検索スニペット参考のみ）|—|search_snippet_reference_only|[価格比較ページ](https://kakaku.com/item/K0001696164/) / [検索ページ参考元](https://search.kakaku.com/PNY%20GeForce%20RTX%205070%20Ti%2016GB%20ARGB/)|

互換性チェック:

- **PASS**: cpu_motherboard_socket — CPU socket AM5 / board socket AM5
- **PASS**: memory_type_capacity_dual_channel — DDR type, >= 32GB, >= 2 DIMMs
- **PASS**: storage_capacity_interface — NVMe SSD 1000GB / minimum 1000GB
- **PASS**: motherboard_case_form_factor — Board MicroATX / case supports ATX, MicroATX, MiniITX
- **REVIEW**: gpu_case_clearance — Exact GPU retail-card length or case clearance must be verified before ordering
- **PASS**: cooler_socket — AM5 mounting support declared
- **PASS**: cooler_case_clearance — Cooler 157mm / case limit 170mm
- **PASS**: psu_wattage — PSU 850W / GPU recommendation 750W
- **PASS**: gpu_power_connector — PSU ATX 3.1 native 12V-2x6 cable
- **PASS**: os_license — Windows 11 Home license budgeted unless an existing transferable license is confirmed

## 注文直前の確認

- CPUソケット／BIOS／マザーボード対応、メモリ規格・QVL・EXPO安定性。
- GPUの正確な小売型番・カード寸法・厚さ・補助電源とケース干渉。
- 電源容量・規格・付属ケーブル、クーラー高とRAM干渉、ファン配置。
- 個別店の決済価格・送料・在庫・返品期限・保証・OSライセンス。
- 比較サイト参考価格は公式BF価格ではない。公式日程・店舗価格が確認できるまで買い時判定は保留。
