# 自作PCパーツ構成・価格監視

更新: 2026-10-25T01:43:45+09:00
予算（すべて日本円）: PC本体基準目標 ¥360,000 / PC本体計画上限 ¥380,000 / PC本体単体の比較上限（総額上限ではない） ¥395,000 / 周辺機器計画枠 ¥35,000 / 総額予備費 ¥5,000 / 総額目標 ¥400,000 / 比較検討帯上限 ¥420,000

**購入方式:** 自作PCを正式な本命として最適化します。組み立て時間・作業時間は減点しません。BTOは同等仕様での総額・部品品質・保証のベンチマークとして比較し、便利さだけを理由に自作から切り替えません。

**注意:** BF購入目標は購入希望額です。比較サイト価格は市場参考値であり、店舗の決済価格・在庫・公式BF実売価格ではありません。現在のデータから購入許可は出しません。

## 用途評価：ゲームを遊ぶだけでなく、ゲーム制作も主要要件

制作対象エンジン: Unreal Engine 5、Unity、Godot
想定プロジェクト: 2D indie games、3D indie games、FPS prototypes、city-builder/simulation games
制作ベースラインはRAM 32GB・専用GPU VRAM 8GB以上・SSD 1TB以上。64GB RAM・2TB SSDは、大きなアセット、ビルド、AI/分析ツールの同時利用に備える本プロジェクト上の優先目標です。予算・価格証拠を満たし、購入時の構成に含まれる場合だけ達成とし、後からの増設は想定しません。
Unreal Engine自体をソースからローカルでフルビルドする用途は別扱いです。Epicの12～16コアという実用的な目安に対し、8コアのRyzen 7 9700Xはここでは妥協点であり、通常のゲームプロジェクト制作が不可という意味ではありません。

|GPU候補|制作評価|RAM|GPU VRAM|SSD|Unreal Engineソースフルビルド|
|---|---|---:|---:|---:|---|
|自作大穴：Ryzen 7 9700X + RTX 5070 Ti 16GB|制作ベースライン適合|32GB|16GB|1000GB|TRADEOFF_BELOW_PRACTICAL_CORE_TARGET|
|自作本命：Ryzen 7 9700X + RTX 5070 12GB|制作ベースライン適合|32GB|12GB|1000GB|TRADEOFF_BELOW_PRACTICAL_CORE_TARGET|
|自作VRAM案：Ryzen 7 9700X + RTX 5060 Ti 16GB|制作ベースライン適合|32GB|16GB|1000GB|TRADEOFF_BELOW_PRACTICAL_CORE_TARGET|

評価対象ゲーム: Cities: Skylines II、Apex Legends、VALORANT、other FPS games
勉強・調査: daily school lessons and class materials、school quizzes and term exams、transfer from school lessons to Waseda University / Kyushu University entrance-exam problem-solving、textbook, worksheet, PDF and source-document reading、first-seen problems, multi-unit transfer, written explanations and timed practice、faculty/admission-route requirements and public past papers verified from official sources、error analysis, delayed re-testing and revision tracking、research, writing, presentations, browser multitasking and video lessons
データ分析・自動化・AI: Python data analysis、large datasets and simulations、sports prediction systems、stock/securities prediction、BTC prediction、GitHub Actions and local tests、AI-assisted workflows、local AI models when feasible
同時利用想定: IDE/ゲームエンジン/Python/テスト/資料閲覧/ブラウザー/AIツール。CPU・RAM・VRAM・SSD・冷却を用途別に確認し、すべての分析処理がGPUで速くなるとは仮定しません。

**メモリ選択:** TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)
選定方法: primary_memory_fallback_no_verified_in_stock_alternative
基本構成では、既定の32GB容量を満たす販売可能な完全一致キットだけを代替比較します。64GBは条件付き置換候補として表示し、全構成へ一律に入れません。40万円は総額目標で、用途上の改善が明確なら42万円までの許容帯を比較し、さらに超える案は45万円シナリオで別評価します。
価格比較では、型番一致・鮮度・PIT条件を満たす直接販売店の掲載価格と在庫を確認します。比較サイト価格は決済価格ではなく、購入許可も意味しません。

- Crucial Pro DDR5-6000 32GB (16GBx2) / BF目標 ¥60,000 / 比較参考 未検証 / 状態 missing / [商品ページ](https://kakaku.com/item/K0001633533/)
- TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2) / BF目標 ¥58,000 / 比較参考 未検証 / 状態 missing / [商品ページ](https://kakaku.com/item/K0001610896/)
- Lexar THOR RGB 2nd Gen DDR5-6000 64GB (32GBx2) / BF目標 ¥100,000 / 比較参考 未検証 / 状態 missing / [商品ページ](https://www.ark-pc.co.jp/i/11650134/)
- Corsair VENGEANCE DDR5-6000 32GB (16GBx2) CL38 EXPO/XMP / BF目標 ¥59,000 / 比較参考 未検証 / 状態 missing / [商品ページ](https://www.corsair.com/jp/ja/p/memory/cmk32gx5m2d6000z38/vengeance-32gb-2-x-16gb-ddr5-dram-up-to-6000mt-s-cl38-amd-expo-%26-intel-xmp-memory-kit-gray-cmk32gx5m2d6000z38)

## 現時点の販売店掲載価格・在庫（BF目標とは別集計）

以下は、商品型番・取得時刻が検証できた直接販売店ページのうち、在庫あり／在庫少と明示された掲載価格だけの部分小計です。注文カートの最終価格ではなく、在庫不明・売り切れ・未取得の部品は合計に埋めません。必須部品すべてに販売可能な掲載価格がそろわない構成は、PC本体価格を算定できません。

|構成|販売可能掲載価格が確認できた部品|部品数カバー率|確認済み掲載価格の部分小計|在庫切れ掲載（売り切れ）|在庫不明掲載|鮮度切れ掲載|販売可能価格が未確認の部品|
|---|---|---:|---:|---:|---:|---:|---|
|自作大穴：Ryzen 7 9700X + RTX 5070 Ti 16GB|3/9|33.3%|¥33,150|2|9|5|AMD Ryzen 7 9700X BOX、ASRock B850M Pro RS WiFi、Microsoft Windows 11 Home 日本語版 パッケージ版、TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)、Crucial P3 Plus CT1000P3PSSD8JP 1TB、PNY GeForce RTX 5070 Ti 16GB ARGB|
|自作本命：Ryzen 7 9700X + RTX 5070 12GB|3/9|33.3%|¥33,150|2|9|6|AMD Ryzen 7 9700X BOX、ASRock B850M Pro RS WiFi、Microsoft Windows 11 Home 日本語版 パッケージ版、TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)、Crucial P3 Plus CT1000P3PSSD8JP 1TB、PNY GeForce RTX 5070 12GB OC SLIM|
|自作VRAM案：Ryzen 7 9700X + RTX 5060 Ti 16GB|4/9|44.4%|¥170,950|1|9|5|AMD Ryzen 7 9700X BOX、ASRock B850M Pro RS WiFi、Microsoft Windows 11 Home 日本語版 パッケージ版、TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)、Crucial P3 Plus CT1000P3PSSD8JP 1TB|

**重要:** 「確認済み掲載価格の部分小計」は全構成の現在価格ではありません。部品ごとの価格時刻・売り切れ状態は下の部品表を確認してください。価格や在庫を取得できないことを「売り切れ」とは推定しません。

## 100点方式の構成スコア（BF目標構成ベース）

構成点は用途適性・目標総額ベースの相対価格効率・互換性で採点。ゲーム点は[Tom's Hardware GPU Benchmarks Hierarchy 2026](https://www.tomshardware.com/reviews/gpu-hierarchy,4388.html)の1440p Ultraラスタライズ値を25点満点に正規化した代理指標で、対象ゲームの実測FPSではありません。参照表の最終更新日は2026-06-24です。GPU参照FPSも各構成に対応させて表示します。
購入根拠充足度は直接価格・型番・取得時刻・販売可能在庫・検証済み決済総額・互換性を別計算し、購入許可とは切り離します。

|順位|構成|GPU参照FPS (1440p Ultra)|総合点/100|ゲーム/25|制作/20|分析・AI/20|勉強・同時利用/10|価格効率/15|互換性/10|購入根拠充足度/100|直接価格・在庫・決済確認率|市場参考値|
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
|1|自作大穴：Ryzen 7 9700X + RTX 5070 Ti 16GB|116.8|86.0|25.0|16.7|12.5|8.0|15.0|8.8|55.9|価格100.0%・在庫33.3%・決済0.0%|3/9|
|2|自作本命：Ryzen 7 9700X + RTX 5070 12GB|96.4|77.5|20.6|14.7|11.2|8.0|13.8|9.2|56.7|価格100.0%・在庫33.3%・決済0.0%|3/9|
|3|自作VRAM案：Ryzen 7 9700X + RTX 5060 Ti 16GB|73.4|76.2|15.7|16.7|12.5|8.0|14.1|9.2|59.5|価格100.0%・在庫44.4%・決済0.0%|4/9|

## 高コア数CPUの比較（補助候補。購入認定ではない）

主ランキングのRyzen 7 9700Xはゲームと一般的な制作・分析を両立する基準構成です。次のCPU案はRTX 5070 12GBを共通GPUとしてCPU差分を比較します。100点スコアは主ランキングと同じ式・価格効率の比較母集団で再計算していますが、互換性・冷却・販売価格の未確認が解消されたことを意味しません。

|全候補順位|CPU比較案|コア/スレッド|CPU BF目標|PC本体BF目標|周辺機器込みBF目標|基準案からの総額差|制作スコア/20|分析スコア/20|総合点/100|互換性|判定|
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
|2|AMD Ryzen 9 9900X BOX|12/24|¥55,000|¥352,000|¥392,000|¥10,000|16.0|13.0|80.7|REVIEW|WAIT_FOR_COMPATIBILITY_REVIEW|

この補助案でもCPUの目標価格だけを使って実売価格を作り出しません。購入前にCPUの正確なSKU・最新の販売可能価格・BIOS・RAM QVL/EXPO・冷却性能・送料・保証を確認します。

|高コア数の大穴|コア/スレッド|CPU BF目標|現行クーラーのままCPU差額だけを置換した総額下限|40万円上限超過（冷却変更前）|冷却・価格の状態|
|---|---:|---:|---:|---:|---|
|AMD Ryzen 9 9950X BOX|16/32|¥85,000|¥422,000|¥2,000|AMD official specification: liquid cooler recommended for optimal performance。冷却費用未算入・完全構成未確認|

上記の総額下限は完全な購入構成ではありません。メーカー推奨の冷却を採用する場合の追加費用を含まず、予算内と誤認しないために別枠で表示しています。

## 目標総額と購入ゲート

|順位|構成|部品目標小計|PC本体目標総額|周辺機器込み目標|目標残額|比較参考合計|互換性|判定|全パーツ商品リンク|
|---:|---|---:|---:|---:|---:|---:|---|---|---|
|1|自作大穴：Ryzen 7 9700X + RTX 5070 Ti 16GB|¥353,000|¥362,000|¥402,000|¥-2,000|未確認|REVIEW|WAIT_FOR_COMPATIBILITY_REVIEW|[AMD Ryzen 7 9700X BOX](https://kakaku.com/item/K0001630332/) / [ASRock B850M Pro RS WiFi](https://kakaku.com/item/K0001669878/) / [Corsair RM850e 2025 850W ATX 3.1 Gold](https://www.dospara.co.jp/SBR83/IC519918.html) / [Fractal Design Pop Air TG](https://www.dospara.co.jp/SBR1959/IC480986.html) / [Microsoft Windows 11 Home 日本語版 パッケージ版](https://kakaku.com/item/K0001432816/) / [TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)](https://kakaku.com/item/K0001610896/) / [Crucial P3 Plus CT1000P3PSSD8JP 1TB](https://kakaku.com/item/K0001466997/) / [Thermalright Peerless Assassin 120 SE V3](https://www.dospara.co.jp/SBR1968/IC645423.html) / [PNY GeForce RTX 5070 Ti 16GB ARGB](https://kakaku.com/item/K0001696164/)|
|2|自作本命：Ryzen 7 9700X + RTX 5070 12GB|¥333,000|¥342,000|¥382,000|¥18,000|未確認|REVIEW|WAIT_FOR_COMPATIBILITY_REVIEW|[AMD Ryzen 7 9700X BOX](https://kakaku.com/item/K0001630332/) / [ASRock B850M Pro RS WiFi](https://kakaku.com/item/K0001669878/) / [Corsair RM850e 2025 850W ATX 3.1 Gold](https://www.dospara.co.jp/SBR83/IC519918.html) / [Fractal Design Pop Air TG](https://www.dospara.co.jp/SBR1959/IC480986.html) / [Microsoft Windows 11 Home 日本語版 パッケージ版](https://kakaku.com/item/K0001432816/) / [TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)](https://kakaku.com/item/K0001610896/) / [Crucial P3 Plus CT1000P3PSSD8JP 1TB](https://kakaku.com/item/K0001466997/) / [Thermalright Peerless Assassin 120 SE V3](https://www.dospara.co.jp/SBR1968/IC645423.html) / [PNY GeForce RTX 5070 12GB OC SLIM](https://kakaku.com/item/K0001798041/)|
|3|自作VRAM案：Ryzen 7 9700X + RTX 5060 Ti 16GB|¥315,000|¥324,000|¥364,000|¥36,000|未確認|REVIEW|WAIT_FOR_COMPATIBILITY_REVIEW|[AMD Ryzen 7 9700X BOX](https://kakaku.com/item/K0001630332/) / [ASRock B850M Pro RS WiFi](https://kakaku.com/item/K0001669878/) / [Corsair RM850e 2025 850W ATX 3.1 Gold](https://www.dospara.co.jp/SBR83/IC519918.html) / [Fractal Design Pop Air TG](https://www.dospara.co.jp/SBR1959/IC480986.html) / [Microsoft Windows 11 Home 日本語版 パッケージ版](https://kakaku.com/item/K0001432816/) / [TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)](https://kakaku.com/item/K0001610896/) / [Crucial P3 Plus CT1000P3PSSD8JP 1TB](https://kakaku.com/item/K0001466997/) / [Thermalright Peerless Assassin 120 SE V3](https://www.dospara.co.jp/SBR1968/IC645423.html) / [PNY GeForce RTX 5060 Ti 16GB OC](https://www.dospara.co.jp/SBR1892/IC625088.html)|

## 35万円・40万円・45万円の一式予算比較（BF目標価格の計画値）

各予算にはPC本体・OS・送料/小物・メインモニター1台と入力機器・必要送料・5,000円予備費を含みます。通常目標と20,000円の検討帯を分けて表示し、検討帯内でも購入許可は出しません。BF目標価格は現行決済価格ではありません。

**用途要件:** Cities: Skylines IIとFPS、Unreal Engine/Unity/Godotによるゲーム制作、Python・スポーツ/株式/BTC分析、可能な範囲のローカルAI、勉強・調査。購入時RAM32GB/SSD1TB/専用VRAM8GB以上を下回る案は採用しません。

### budget_350k（総額目標 ¥350,000 / 許容帯上限 ¥370,000）

35万円目標案。必要周辺機器・送料・5,000円予備費込み。総額37万円までの許容帯で、目標超過額と性能差を比較する。

|順位|構成案|CPU|GPU / VRAM|RAM|SSD|PC本体目標|周辺機器|予備費|一式目標|目標との差/残額|目標超過額|許容帯残額/超過|許容帯内|総合点/100|販売可能在庫信号|互換性|購入判定|
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|---|
|1|35万円本命：Ryzen 7 7700 + RTX 5060 Ti 16GB|AMD Ryzen 7 7700 BOX (Wraith Stealth Cooler)|PNY GeForce RTX 5060 Ti 16GB OC / 16GB|32GB|1000GB|¥308,000|¥35,000|¥5,000|¥348,000|残り ¥2,000|¥0|残り ¥22,000|はい|76.5|3/8部品|REVIEW|WAIT_FOR_COMPATIBILITY_REVIEW|
|2|35万円比較：Ryzen 7 7700 + RTX 5070 12GB（予算超過）|AMD Ryzen 7 7700 BOX (Wraith Stealth Cooler)|PNY GeForce RTX 5070 12GB OC SLIM / 12GB|32GB|1000GB|¥326,000|¥35,000|¥5,000|¥366,000|超過 ¥16,000|¥16,000|残り ¥4,000|はい|77.8|2/8部品|REVIEW|WAIT_FOR_COMPATIBILITY_REVIEW|

#### 部品内訳・用途のトレードオフ

**35万円本命：Ryzen 7 7700 + RTX 5060 Ti 16GB — 76.5点/100**
- 一式目標 ¥348,000。8コア/16スレッド、32GB RAM、16GB VRAM、1TB NVMeを購入時点で維持する予算優先案。
- 部品目標の内訳: [AMD Ryzen 7 7700 BOX (Wraith Stealth Cooler)](https://kakaku.com/item/K0001711744/) ¥35,000、[ASRock B650M Pro X3D WiFi](https://kakaku.com/item/K0001679617/) ¥19,000、[PNY GeForce RTX 5060 Ti 16GB OC](https://www.dospara.co.jp/SBR1892/IC625088.html) ¥120,000、[TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)](https://kakaku.com/item/K0001610896/) ¥58,000、[Crucial P3 Plus CT1000P3PSSD8JP 1TB](https://kakaku.com/item/K0001466997/) ¥24,000、[Corsair RM850e 2025 850W ATX 3.1 Gold](https://www.dospara.co.jp/SBR83/IC519918.html) ¥14,000、[Fractal Design Pop Air TG](https://www.dospara.co.jp/SBR1959/IC480986.html) ¥12,000、[Microsoft Windows 11 Home 日本語版 パッケージ版](https://kakaku.com/item/K0001432816/) ¥17,000。
- 留意点: 9700X/RTX 5070より処理余裕・ゲーム描画は低い。付属クーラーの長時間負荷時の音・温度を確認。
- 販売可能在庫信号: 3/8部品。直接価格・在庫・最終決済額がそろわない限り、目標総額が予算内でも購入可能とは判定しません。互換性=REVIEW。購入許可=false。

**35万円比較：Ryzen 7 7700 + RTX 5070 12GB（予算超過） — 77.8点/100**
- 一式目標 ¥366,000。RTX 5070を選んだ場合の性能差と必要予算を比較する参考案。
- 部品目標の内訳: [AMD Ryzen 7 7700 BOX (Wraith Stealth Cooler)](https://kakaku.com/item/K0001711744/) ¥35,000、[ASRock B650M Pro X3D WiFi](https://kakaku.com/item/K0001679617/) ¥19,000、[PNY GeForce RTX 5070 12GB OC SLIM](https://kakaku.com/item/K0001798041/) ¥138,000、[TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)](https://kakaku.com/item/K0001610896/) ¥58,000、[Crucial P3 Plus CT1000P3PSSD8JP 1TB](https://kakaku.com/item/K0001466997/) ¥24,000、[Corsair RM850e 2025 850W ATX 3.1 Gold](https://www.dospara.co.jp/SBR83/IC519918.html) ¥14,000、[Fractal Design Pop Air TG](https://www.dospara.co.jp/SBR1959/IC480986.html) ¥12,000、[Microsoft Windows 11 Home 日本語版 パッケージ版](https://kakaku.com/item/K0001432816/) ¥17,000。
- 留意点: 目標構成でも総額35万円を16,000円超過。GPU以外を無理に削って適合扱いしない。
- 販売可能在庫信号: 2/8部品。直接価格・在庫・最終決済額がそろわない限り、目標総額が予算内でも購入可能とは判定しません。互換性=REVIEW。購入許可=false。


### budget_400k（総額目標 ¥400,000 / 許容帯上限 ¥420,000）

40万円目標案（本命）。必要周辺機器・送料・5,000円予備費込み。総額42万円までの許容帯で、数万円の超過だけでは候補を落とさない。

|順位|構成案|CPU|GPU / VRAM|RAM|SSD|PC本体目標|周辺機器|予備費|一式目標|目標との差/残額|目標超過額|許容帯残額/超過|許容帯内|総合点/100|販売可能在庫信号|互換性|購入判定|
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|---|
|1|40万円容量案：Ryzen 7 9700X + RTX 5060 Ti 16GB + 2TB|AMD Ryzen 7 9700X BOX|PNY GeForce RTX 5060 Ti 16GB OC / 16GB|32GB|2000GB|¥345,000|¥35,000|¥5,000|¥385,000|残り ¥15,000|¥0|残り ¥35,000|はい|79.2|4/9部品|REVIEW|WAIT_FOR_COMPATIBILITY_REVIEW|
|2|40万円本命：Ryzen 7 9700X + RTX 5070 12GB|AMD Ryzen 7 9700X BOX|PNY GeForce RTX 5070 12GB OC SLIM / 12GB|32GB|1000GB|¥342,000|¥35,000|¥5,000|¥382,000|残り ¥18,000|¥0|残り ¥38,000|はい|77.5|3/9部品|REVIEW|WAIT_FOR_COMPATIBILITY_REVIEW|
|3|40万円大穴：RTX 5070 Ti 16GB（目標では予算超過）|AMD Ryzen 7 9700X BOX|PNY GeForce RTX 5070 Ti 16GB ARGB / 16GB|32GB|1000GB|¥362,000|¥35,000|¥5,000|¥402,000|超過 ¥2,000|¥2,000|残り ¥18,000|はい|86.0|3/9部品|REVIEW|WAIT_FOR_COMPATIBILITY_REVIEW|

#### 部品内訳・用途のトレードオフ

**40万円容量案：Ryzen 7 9700X + RTX 5060 Ti 16GB + 2TB — 79.2点/100**
- 一式目標 ¥385,000。16GB VRAMと2TB NVMeを購入時点で確保。
- 部品目標の内訳: [AMD Ryzen 7 9700X BOX](https://kakaku.com/item/K0001630332/) ¥45,000、[ASRock B850M Pro RS WiFi](https://kakaku.com/item/K0001669878/) ¥20,000、[PNY GeForce RTX 5060 Ti 16GB OC](https://www.dospara.co.jp/SBR1892/IC625088.html) ¥120,000、[TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)](https://kakaku.com/item/K0001610896/) ¥58,000、[KIOXIA EXCERIA BASIC SSD-CK2.0N4B/N 2TB](https://kakaku.com/item/K0001719361/) ¥45,000、[Corsair RM850e 2025 850W ATX 3.1 Gold](https://www.dospara.co.jp/SBR83/IC519918.html) ¥14,000、[Fractal Design Pop Air TG](https://www.dospara.co.jp/SBR1959/IC480986.html) ¥12,000、[Thermalright Peerless Assassin 120 SE V3](https://www.dospara.co.jp/SBR1968/IC645423.html) ¥5,000、[Microsoft Windows 11 Home 日本語版 パッケージ版](https://kakaku.com/item/K0001432816/) ¥17,000。
- 留意点: RTX 5070よりゲーム描画は低くなり得る。KIOXIAのQLC NANDは持続書込み負荷との適合も確認。
- 販売可能在庫信号: 4/9部品。直接価格・在庫・最終決済額がそろわない限り、目標総額が予算内でも購入可能とは判定しません。互換性=REVIEW。購入許可=false。

**40万円本命：Ryzen 7 9700X + RTX 5070 12GB — 77.5点/100**
- 一式目標 ¥382,000。ゲーム、ゲーム制作、分析、勉強を広く両立する基準構成。
- 部品目標の内訳: [AMD Ryzen 7 9700X BOX](https://kakaku.com/item/K0001630332/) ¥45,000、[ASRock B850M Pro RS WiFi](https://kakaku.com/item/K0001669878/) ¥20,000、[PNY GeForce RTX 5070 12GB OC SLIM](https://kakaku.com/item/K0001798041/) ¥138,000、[TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)](https://kakaku.com/item/K0001610896/) ¥58,000、[Crucial P3 Plus CT1000P3PSSD8JP 1TB](https://kakaku.com/item/K0001466997/) ¥24,000、[Corsair RM850e 2025 850W ATX 3.1 Gold](https://www.dospara.co.jp/SBR83/IC519918.html) ¥14,000、[Fractal Design Pop Air TG](https://www.dospara.co.jp/SBR1959/IC480986.html) ¥12,000、[Thermalright Peerless Assassin 120 SE V3](https://www.dospara.co.jp/SBR1968/IC645423.html) ¥5,000、[Microsoft Windows 11 Home 日本語版 パッケージ版](https://kakaku.com/item/K0001432816/) ¥17,000。
- 留意点: 標準ではRAM64GB/SSD2TBを含めない。価格と互換性の最終確認を優先。
- 販売可能在庫信号: 3/9部品。直接価格・在庫・最終決済額がそろわない限り、目標総額が予算内でも購入可能とは判定しません。互換性=REVIEW。購入許可=false。

**40万円大穴：RTX 5070 Ti 16GB（目標では予算超過） — 86.0点/100**
- 一式目標 ¥402,000。最高いGPU性能と16GB VRAMを狙う参考案。
- 部品目標の内訳: [AMD Ryzen 7 9700X BOX](https://kakaku.com/item/K0001630332/) ¥45,000、[ASRock B850M Pro RS WiFi](https://kakaku.com/item/K0001669878/) ¥20,000、[PNY GeForce RTX 5070 Ti 16GB ARGB](https://kakaku.com/item/K0001696164/) ¥158,000、[TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)](https://kakaku.com/item/K0001610896/) ¥58,000、[Crucial P3 Plus CT1000P3PSSD8JP 1TB](https://kakaku.com/item/K0001466997/) ¥24,000、[Corsair RM850e 2025 850W ATX 3.1 Gold](https://www.dospara.co.jp/SBR83/IC519918.html) ¥14,000、[Fractal Design Pop Air TG](https://www.dospara.co.jp/SBR1959/IC480986.html) ¥12,000、[Thermalright Peerless Assassin 120 SE V3](https://www.dospara.co.jp/SBR1968/IC645423.html) ¥5,000、[Microsoft Windows 11 Home 日本語版 パッケージ版](https://kakaku.com/item/K0001432816/) ¥17,000。
- 留意点: 目標で総額2,000円超過。2.98スロット厚、補助電源配線とケース周囲クリアランスはREVIEW。
- 販売可能在庫信号: 3/9部品。直接価格・在庫・最終決済額がそろわない限り、目標総額が予算内でも購入可能とは判定しません。互換性=REVIEW。購入許可=false。


### budget_450k（総額目標 ¥450,000 / 許容帯上限 ¥470,000）

45万円目標案。必要周辺機器・送料・5,000円予備費込み。総額47万円までの許容帯。GPUだけでなく64GB RAM・2TB SSD・高コアCPUの実益を比較する。

|順位|構成案|CPU|GPU / VRAM|RAM|SSD|PC本体目標|周辺機器|予備費|一式目標|目標との差/残額|目標超過額|許容帯残額/超過|許容帯内|総合点/100|販売可能在庫信号|互換性|購入判定|
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|---|
|1|45万円GPU案：RTX 5070 Ti 16GB + 64GB RAM|AMD Ryzen 7 9700X BOX|PNY GeForce RTX 5070 Ti 16GB ARGB / 16GB|64GB|1000GB|¥404,000|¥35,000|¥5,000|¥444,000|残り ¥6,000|¥0|残り ¥26,000|はい|90.7|3/9部品|REVIEW|WAIT_FOR_COMPATIBILITY_REVIEW|
|2|45万円GPU+容量案：RTX 5070 Ti 16GB + 2TB SSD|AMD Ryzen 7 9700X BOX|PNY GeForce RTX 5070 Ti 16GB ARGB / 16GB|32GB|2000GB|¥383,000|¥35,000|¥5,000|¥423,000|残り ¥27,000|¥0|残り ¥47,000|はい|89.0|3/9部品|REVIEW|WAIT_FOR_COMPATIBILITY_REVIEW|
|3|45万円総合案：RTX 5070 + 64GB RAM + 2TB SSD|AMD Ryzen 7 9700X BOX|PNY GeForce RTX 5070 12GB OC SLIM / 12GB|64GB|2000GB|¥405,000|¥35,000|¥5,000|¥445,000|残り ¥5,000|¥0|残り ¥25,000|はい|85.4|3/9部品|REVIEW|WAIT_FOR_COMPATIBILITY_REVIEW|
|4|45万円分析案：RTX 5070 + 64GB RAM + 1TB SSD|AMD Ryzen 7 9700X BOX|PNY GeForce RTX 5070 12GB OC SLIM / 12GB|64GB|1000GB|¥384,000|¥35,000|¥5,000|¥424,000|残り ¥26,000|¥0|残り ¥46,000|はい|82.4|3/9部品|REVIEW|WAIT_FOR_COMPATIBILITY_REVIEW|
|5|45万円上位大穴：Ryzen 7 9700X + RTX 5070 Ti 16GB + 64GB RAM + 2TB SSD|AMD Ryzen 7 9700X BOX|PNY GeForce RTX 5070 Ti 16GB ARGB / 16GB|64GB|2000GB|¥425,000|¥35,000|¥5,000|¥465,000|超過 ¥15,000|¥15,000|残り ¥5,000|はい|93.7|3/9部品|REVIEW|WAIT_FOR_COMPATIBILITY_REVIEW|
|6|45万円CPU並列案：Ryzen 9 9900X + RTX 5070 12GB + 64GB RAM + 2TB SSD|AMD Ryzen 9 9900X BOX|PNY GeForce RTX 5070 12GB OC SLIM / 12GB|64GB|2000GB|¥415,000|¥35,000|¥5,000|¥455,000|超過 ¥5,000|¥5,000|残り ¥15,000|はい|88.5|3/9部品|REVIEW|WAIT_FOR_COMPATIBILITY_REVIEW|

#### 部品内訳・用途のトレードオフ

**45万円GPU案：RTX 5070 Ti 16GB + 64GB RAM — 90.7点/100**
- 一式目標 ¥444,000。GPUレンダリング/ゲーム性能とRAM64GBを優先。
- 部品目標の内訳: [AMD Ryzen 7 9700X BOX](https://kakaku.com/item/K0001630332/) ¥45,000、[ASRock B850M Pro RS WiFi](https://kakaku.com/item/K0001669878/) ¥20,000、[PNY GeForce RTX 5070 Ti 16GB ARGB](https://kakaku.com/item/K0001696164/) ¥158,000、[Lexar THOR RGB 2nd Gen DDR5-6000 64GB (32GBx2)](https://www.ark-pc.co.jp/i/11650134/) ¥100,000、[Crucial P3 Plus CT1000P3PSSD8JP 1TB](https://kakaku.com/item/K0001466997/) ¥24,000、[Corsair RM850e 2025 850W ATX 3.1 Gold](https://www.dospara.co.jp/SBR83/IC519918.html) ¥14,000、[Fractal Design Pop Air TG](https://www.dospara.co.jp/SBR1959/IC480986.html) ¥12,000、[Thermalright Peerless Assassin 120 SE V3](https://www.dospara.co.jp/SBR1968/IC645423.html) ¥5,000、[Microsoft Windows 11 Home 日本語版 パッケージ版](https://kakaku.com/item/K0001432816/) ¥17,000。
- 留意点: SSDは1TB。RTX 5070 Tiの厚さ、電源ケーブル、RAM QVLと全決済価格を確認。
- 販売可能在庫信号: 3/9部品。直接価格・在庫・最終決済額がそろわない限り、目標総額が予算内でも購入可能とは判定しません。互換性=REVIEW。購入許可=false。

**45万円GPU+容量案：RTX 5070 Ti 16GB + 2TB SSD — 89.0点/100**
- 一式目標 ¥423,000。GPU性能・16GB VRAM・2TB SSDを優先する別案。
- 部品目標の内訳: [AMD Ryzen 7 9700X BOX](https://kakaku.com/item/K0001630332/) ¥45,000、[ASRock B850M Pro RS WiFi](https://kakaku.com/item/K0001669878/) ¥20,000、[PNY GeForce RTX 5070 Ti 16GB ARGB](https://kakaku.com/item/K0001696164/) ¥158,000、[TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)](https://kakaku.com/item/K0001610896/) ¥58,000、[KIOXIA EXCERIA BASIC SSD-CK2.0N4B/N 2TB](https://kakaku.com/item/K0001719361/) ¥45,000、[Corsair RM850e 2025 850W ATX 3.1 Gold](https://www.dospara.co.jp/SBR83/IC519918.html) ¥14,000、[Fractal Design Pop Air TG](https://www.dospara.co.jp/SBR1959/IC480986.html) ¥12,000、[Thermalright Peerless Assassin 120 SE V3](https://www.dospara.co.jp/SBR1968/IC645423.html) ¥5,000、[Microsoft Windows 11 Home 日本語版 パッケージ版](https://kakaku.com/item/K0001432816/) ¥17,000。
- 留意点: RAMは基準の32GB。予算余裕があってもRAM QVLと実価格の条件を確認して選ぶ。
- 販売可能在庫信号: 3/9部品。直接価格・在庫・最終決済額がそろわない限り、目標総額が予算内でも購入可能とは判定しません。互換性=REVIEW。購入許可=false。

**45万円総合案：RTX 5070 + 64GB RAM + 2TB SSD — 85.4点/100**
- 一式目標 ¥445,000。ゲーム性能を保ちつつ、ゲーム制作素材・ビルド・Pythonと分析データの同時利用に向けRAM64GBとSSD2TBを購入時点で確保。
- 部品目標の内訳: [AMD Ryzen 7 9700X BOX](https://kakaku.com/item/K0001630332/) ¥45,000、[ASRock B850M Pro RS WiFi](https://kakaku.com/item/K0001669878/) ¥20,000、[PNY GeForce RTX 5070 12GB OC SLIM](https://kakaku.com/item/K0001798041/) ¥138,000、[Lexar THOR RGB 2nd Gen DDR5-6000 64GB (32GBx2)](https://www.ark-pc.co.jp/i/11650134/) ¥100,000、[KIOXIA EXCERIA BASIC SSD-CK2.0N4B/N 2TB](https://kakaku.com/item/K0001719361/) ¥45,000、[Corsair RM850e 2025 850W ATX 3.1 Gold](https://www.dospara.co.jp/SBR83/IC519918.html) ¥14,000、[Fractal Design Pop Air TG](https://www.dospara.co.jp/SBR1959/IC480986.html) ¥12,000、[Thermalright Peerless Assassin 120 SE V3](https://www.dospara.co.jp/SBR1968/IC645423.html) ¥5,000、[Microsoft Windows 11 Home 日本語版 パッケージ版](https://kakaku.com/item/K0001432816/) ¥17,000。
- 留意点: RTX 5070 TiほどGPU性能は高くない。正確なRAM QVL/EXPO・SSD持続書込適合・現行価格を確認。
- 販売可能在庫信号: 3/9部品。直接価格・在庫・最終決済額がそろわない限り、目標総額が予算内でも購入可能とは判定しません。互換性=REVIEW。購入許可=false。

**45万円分析案：RTX 5070 + 64GB RAM + 1TB SSD — 82.4点/100**
- 一式目標 ¥424,000。RAM容量とCPU並列作業を優先して64GBを購入時点で確保。
- 部品目標の内訳: [AMD Ryzen 7 9700X BOX](https://kakaku.com/item/K0001630332/) ¥45,000、[ASRock B850M Pro RS WiFi](https://kakaku.com/item/K0001669878/) ¥20,000、[PNY GeForce RTX 5070 12GB OC SLIM](https://kakaku.com/item/K0001798041/) ¥138,000、[Lexar THOR RGB 2nd Gen DDR5-6000 64GB (32GBx2)](https://www.ark-pc.co.jp/i/11650134/) ¥100,000、[Crucial P3 Plus CT1000P3PSSD8JP 1TB](https://kakaku.com/item/K0001466997/) ¥24,000、[Corsair RM850e 2025 850W ATX 3.1 Gold](https://www.dospara.co.jp/SBR83/IC519918.html) ¥14,000、[Fractal Design Pop Air TG](https://www.dospara.co.jp/SBR1959/IC480986.html) ¥12,000、[Thermalright Peerless Assassin 120 SE V3](https://www.dospara.co.jp/SBR1968/IC645423.html) ¥5,000、[Microsoft Windows 11 Home 日本語版 パッケージ版](https://kakaku.com/item/K0001432816/) ¥17,000。
- 留意点: SSDは1TBに留まるため、ゲーム素材やデータセット容量と比較。
- 販売可能在庫信号: 3/9部品。直接価格・在庫・最終決済額がそろわない限り、目標総額が予算内でも購入可能とは判定しません。互換性=REVIEW。購入許可=false。

**45万円上位大穴：Ryzen 7 9700X + RTX 5070 Ti 16GB + 64GB RAM + 2TB SSD — 93.7点/100**
- 一式目標 ¥465,000。GPU性能・16GB VRAM・RAM 64GB・SSD 2TBを一度に確保する45万円帯の上位大穴。ゲーム、ゲーム制作アセット、ローカルAI、データ分析、並行開発を広く狙う。
- 部品目標の内訳: [AMD Ryzen 7 9700X BOX](https://kakaku.com/item/K0001630332/) ¥45,000、[ASRock B850M Pro RS WiFi](https://kakaku.com/item/K0001669878/) ¥20,000、[PNY GeForce RTX 5070 Ti 16GB ARGB](https://kakaku.com/item/K0001696164/) ¥158,000、[Lexar THOR RGB 2nd Gen DDR5-6000 64GB (32GBx2)](https://www.ark-pc.co.jp/i/11650134/) ¥100,000、[KIOXIA EXCERIA BASIC SSD-CK2.0N4B/N 2TB](https://kakaku.com/item/K0001719361/) ¥45,000、[Corsair RM850e 2025 850W ATX 3.1 Gold](https://www.dospara.co.jp/SBR83/IC519918.html) ¥14,000、[Fractal Design Pop Air TG](https://www.dospara.co.jp/SBR1959/IC480986.html) ¥12,000、[Thermalright Peerless Assassin 120 SE V3](https://www.dospara.co.jp/SBR1968/IC645423.html) ¥5,000、[Microsoft Windows 11 Home 日本語版 パッケージ版](https://kakaku.com/item/K0001432816/) ¥17,000。
- 留意点: BF目標額ベースの一式目標は465,000円で、45万円目標を15,000円超える一方、47万円の比較帯内には5,000円の余裕がある。実売価格ではない。SSDはQLC NANDのため大規模な持続書き込み速度をTLC候補と比較。RAM QVL/EXPO、GPU実SKU寸法/電源ケーブル余裕、BIOS、全パーツ在庫・最終決済額が未確認の間は購入可能扱いしない。
- 販売可能在庫信号: 3/9部品。直接価格・在庫・最終決済額がそろわない限り、目標総額が予算内でも購入可能とは判定しません。互換性=REVIEW。購入許可=false。

**45万円CPU並列案：Ryzen 9 9900X + RTX 5070 12GB + 64GB RAM + 2TB SSD — 88.5点/100**
- 一式目標 ¥455,000。12コア/24スレッドでローカルビルド・並列分析の余裕を確保しながら、RTX 5070 12GB・RAM 64GB・SSD 2TBを購入時点で狙うCPU並列重視案。
- 部品目標の内訳: [AMD Ryzen 9 9900X BOX](https://kakaku.com/item/K0001630331/) ¥55,000、[ASRock B850M Pro RS WiFi](https://kakaku.com/item/K0001669878/) ¥20,000、[PNY GeForce RTX 5070 12GB OC SLIM](https://kakaku.com/item/K0001798041/) ¥138,000、[Lexar THOR RGB 2nd Gen DDR5-6000 64GB (32GBx2)](https://www.ark-pc.co.jp/i/11650134/) ¥100,000、[KIOXIA EXCERIA BASIC SSD-CK2.0N4B/N 2TB](https://kakaku.com/item/K0001719361/) ¥45,000、[Corsair RM850e 2025 850W ATX 3.1 Gold](https://www.dospara.co.jp/SBR83/IC519918.html) ¥14,000、[Fractal Design Pop Air TG](https://www.dospara.co.jp/SBR1959/IC480986.html) ¥12,000、[Thermalright Peerless Assassin 120 SE V3](https://www.dospara.co.jp/SBR1968/IC645423.html) ¥5,000、[Microsoft Windows 11 Home 日本語版 パッケージ版](https://kakaku.com/item/K0001432816/) ¥17,000。
- 留意点: CPU目標55,000円、RAM/SSD/GPUもBF目標を使った計画値で、実売ではない。9900Xは120W TDPでAMDは最適性能のため液冷を推奨するため、Peerless Assassin空冷での長時間全コア負荷時の温度・騒音・クロックを検証する。冷却変更が必要なら未計上費を追加し、総額を再計算する。メモリQVL/EXPO・GPU寸法/電源・BIOS・全SKUの実売/在庫を確認するまで購入可能扱いしない。
- 販売可能在庫信号: 3/9部品。直接価格・在庫・最終決済額がそろわない限り、目標総額が予算内でも購入可能とは判定しません。互換性=REVIEW。購入許可=false。


## 現在の在庫・売り切れリスク（購入可能総額ではない）

この表は最新スナップショットの、型番一致した販売店掲載の観測です。価格・在庫は注文時に変わる可能性があります。売り切れ価格は販売可能額に加算せず、取得失敗・在庫不明は売り切れと断定しません。

|構成|販売可能掲載を確認|うち在庫少|監視先すべて売切れ|在庫未確認/未取得|販売可能掲載の部分合計|完成総額|
|---|---:|---:|---:|---:|---:|---|
|自作大穴：Ryzen 7 9700X + RTX 5070 Ti 16GB|3/9|0|1|5|¥33,150（掲載価格のみ）|未算出（全パーツ・送料・決済条件の確認が必要）|

- 自作大穴：Ryzen 7 9700X + RTX 5070 Ti 16GB — 在庫少: なし / 監視先すべて売切れ: PNY GeForce RTX 5070 Ti 16GB ARGB / 在庫未確認・未取得: AMD Ryzen 7 9700X BOX、ASRock B850M Pro RS WiFi、Microsoft Windows 11 Home 日本語版 パッケージ版、TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)、Crucial P3 Plus CT1000P3PSSD8JP 1TB
- 販売可能掲載の部分合計は3部品分。完成PC価格でも、送料・一括決済済み金額でもありません。
|自作本命：Ryzen 7 9700X + RTX 5070 12GB|3/9|0|0|6|¥33,150（掲載価格のみ）|未算出（全パーツ・送料・決済条件の確認が必要）|

- 自作本命：Ryzen 7 9700X + RTX 5070 12GB — 在庫少: なし / 監視先すべて売切れ: なし / 在庫未確認・未取得: AMD Ryzen 7 9700X BOX、ASRock B850M Pro RS WiFi、Microsoft Windows 11 Home 日本語版 パッケージ版、TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)、Crucial P3 Plus CT1000P3PSSD8JP 1TB、PNY GeForce RTX 5070 12GB OC SLIM
- 販売可能掲載の部分合計は3部品分。完成PC価格でも、送料・一括決済済み金額でもありません。
|自作VRAM案：Ryzen 7 9700X + RTX 5060 Ti 16GB|4/9|0|0|5|¥170,950（掲載価格のみ）|未算出（全パーツ・送料・決済条件の確認が必要）|

- 自作VRAM案：Ryzen 7 9700X + RTX 5060 Ti 16GB — 在庫少: なし / 監視先すべて売切れ: なし / 在庫未確認・未取得: AMD Ryzen 7 9700X BOX、ASRock B850M Pro RS WiFi、Microsoft Windows 11 Home 日本語版 パッケージ版、TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)、Crucial P3 Plus CT1000P3PSSD8JP 1TB
- 販売可能掲載の部分合計は4部品分。完成PC価格でも、送料・一括決済済み金額でもありません。

## 売り切れ時の代替候補（自動注文なし・型番別に再検証）

代替SKUへの切り替えは、同じ規格/クラスか、正確な型番、最新の直接価格、販売可能在庫、互換性が検証できた場合だけ計画上で行います。低在庫は売り切れリスクとして別途示し、在庫不明を在庫ありと扱いません。

|カテゴリ|候補|部品適合点/100（内訳）|適合の理由・留意点|目標価格|販売可能な直接掲載|在庫信号|比較サイト参考（在庫・購入可否の根拠ではない）|選定ルール|商品ページ|
|---|---|---:|---|---:|---:|---|---|---|---|
|メモリ|Crucial Pro DDR5-6000 32GB (16GBx2)|80/100（用途34/40・余裕16/25・品質17/20・構成13/15）|根拠: 32GB・16GB×2・DDR5-6000の基本要件を満たし、主メモリの代替候補となる。 / 留意: 64GBより容量余裕は小さく、正確な型番のQVL・EXPO安定性は未確認。比較価格だけでは購入可能性を示さない。|¥60,000|販売可能価格なし|在庫未確認|未検証/未取得|検証済み在庫あり候補の価格比較|[商品ページ](https://kakaku.com/item/K0001633533/)|
|メモリ|TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)（選定中）|79/100（用途34/40・余裕16/25・品質16/20・構成13/15）|根拠: 32GB・16GB×2・DDR5-6000で、購入時点の必須要件とデュアルチャネル計画を満たす。 / 留意: 大きなゲーム制作・複数ツール・データ処理を同時に行う場合の余裕は64GBより小さい。正確なQVL/EXPO安定性は要確認。|¥58,000|販売可能価格なし|在庫未確認|未検証/未取得|検証済み在庫あり候補の価格比較|[商品ページ](https://kakaku.com/item/K0001610896/)|
|メモリ|Lexar THOR RGB 2nd Gen DDR5-6000 64GB (32GBx2)|91/100（用途38/40・余裕25/25・品質16/20・構成12/15）|根拠: 64GB・32GB×2で、大型アセット・ビルド・分析ツールの同時利用に最も余裕があるメモリ案。 / 留意: 計画価格では総額40万円を超える組み合わせがある。32GBキットと同時購入せず置換とし、QVLと実総額を確認する。|¥100,000|販売可能価格なし|在庫未確認|未検証/未取得|検証済み在庫あり候補の価格比較|[商品ページ](https://www.ark-pc.co.jp/i/11650134/)|
|メモリ|Corsair VENGEANCE DDR5-6000 32GB (16GBx2) CL38 EXPO/XMP|83/100（用途35/40・余裕16/25・品質18/20・構成14/15）|根拠: 32GB・16GB×2・DDR5-6000 CL38の代替候補で、EXPO/XMP双方の表記がある。 / 留意: 32GBのため64GBより制作・分析の余裕は小さい。正確なキットのマザーボードQVLを購入前に確認する。|¥59,000|販売可能価格なし|在庫未確認|未検証/未取得|検証済み在庫あり候補の価格比較|[商品ページ](https://www.corsair.com/jp/ja/p/memory/cmk32gx5m2d6000z38/vengeance-32gb-2-x-16gb-ddr5-dram-up-to-6000mt-s-cl38-amd-expo-%26-intel-xmp-memory-kit-gray-cmk32gx5m2d6000z38)|
|SSD|Crucial P3 Plus CT1000P3PSSD8JP 1TB（選定中）|75/100（用途34/40・余裕14/25・品質13/20・構成14/15）|根拠: 1TB NVMeでOS・開発環境・ゲームを入れる購入時の最低容量要件を満たす。 / 留意: QLC系で長時間の大容量書込みや書込み耐久を最優先する用途にはより適した候補と比較が必要。速度表記だけで持続性能を保証しない。|¥24,000|販売可能価格なし|在庫未確認|未検証/未取得|優先SSDが買えなければ、在庫確認済みの1TB NVMeへ切替|[商品ページ](https://kakaku.com/item/K0001466997/)|
|SSD|MSI SPATIUM M450 PCIe 4.0 NVMe M.2 1TB V1|72/100（用途31/40・余裕13/25・品質14/20・構成14/15）|根拠: 1TB NVMeの最低容量要件を満たす代替候補で、標準的なOS・ゲーム・開発用途に使える。 / 留意: 主候補より性能や耐久が高いとは仮定しない。正確なSKU・保証・持続書込み特性と決済額を購入前に確認する。|¥25,000|販売可能価格なし|在庫未確認|未検証/未取得|優先SSDが買えなければ、在庫確認済みの1TB NVMeへ切替|[商品ページ](https://www.yodobashi.com/product/100000001009402658/)|
|CPUクーラー|Thermalright Peerless Assassin 120 SE V3（選定中）|91/100（用途37/40・余裕23/25・品質17/20・構成14/15）|根拠: デュアルタワー空冷でCPUの持続負荷や長いビルドに備えやすい。 / 留意: AM5金具、ケース高、メモリ干渉、実装手順、正確な商品リビジョンを確認するまで互換性は確定扱いにしない。|¥5,000|¥4,970|在庫あり（再確認必須）|¥4,970（比較参考のみ・在庫証拠ではない）|優先クーラーが買えなければ、互換性を確認した代替へ切替|[商品ページ](https://www.dospara.co.jp/SBR1968/IC645423.html)|
|CPUクーラー|Thermalright Assassin X 120 Refined SE|78/100（用途33/40・余裕17/25・品質15/20・構成13/15）|根拠: 低コストなシングルタワー空冷代替で、組立費用を抑えやすい。 / 留意: デュアルタワー候補より熱余裕が小さい可能性がある。CPU長時間負荷・ケース/メモリ干渉を確認して置換する。|¥2,500|販売可能価格なし|在庫未確認|未検証/未取得|優先クーラーが買えなければ、互換性を確認した代替へ切替|[商品ページ](https://www.yodobashi.com/product/100000001008996814/)|
|GPU代替|MSI GeForce RTX 5070 12G VENTUS 2X OC|86/100（用途36/40・余裕22/25・品質16/20・構成12/15）|根拠: RTX 5070 12GBクラスの用途バランスを維持できる売切れ時のSKU代替候補。 / 留意: 同一GPUクラスでもカード寸法・厚さ・冷却・端子・在庫は別物。正確なSKUでケースと電源への適合を再確認する。|¥138,000|販売可能価格なし|在庫未確認|未検証/未取得|同じGPUクラスの別SKU。寸法・端子・冷却を再確認|[商品ページ](https://shop.tsukumo.co.jp/goods/4711377308229/)|

## 構成別の詳細


### 自作大穴：Ryzen 7 9700X + RTX 5070 Ti 16GB

- BF目標総額（計画値）: ¥402,000。値下がり予測・実売の確定額ではない。
- 現時点の販売可能掲載: 3/9部品 / 部分合計 ¥33,150（掲載額だけ。完成価格・注文カート合計ではない）。
- 採用GPU SKU: PNY GeForce RTX 5070 Ti 16GB ARGB（primary_exact_sku_fallback_no_verified_in_stock_alternative）
- 採用RAM: TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)（primary_memory_fallback_no_verified_in_stock_alternative）
- 採用SSD: Crucial P3 Plus CT1000P3PSSD8JP 1TB（primary_fallback_no_verified_in_stock_alternative）
- 採用CPUクーラー: Thermalright Peerless Assassin 120 SE V3（keep_primary_if_fresh_in_stock）
- 現在の比較参考合計: 未算出。価格・型番・在庫条件を満たさない部品を0円補完しない
- 互換性: REVIEW / 判定: WAIT_FOR_COMPATIBILITY_REVIEW

部品適合点/100は用途適合40・性能/容量余裕25・品質/信頼性20・構成/拡張性15点のルーブリックから計算します。理由と制約を併記し、未入力・範囲外は未採点です。構成全体の点数や実測ベンチマークではありません。
部品購入根拠点/100は直接価格・在庫・決済総額・その部品に関係する互換性確認・保証/返品条件から動的計算します。適合点とは別で、比較サイト価格や未確認の在庫では加点しません。どちらの点数も購入許可ではありません。

|画像|部品|部品適合点/100（内訳）|部品購入根拠点/100|型番|適合評価の理由・制約|BF目標|検証済み/表示専用参考値|直接掲載価格（在庫条件未達・推定不採用）|確認状態|前倒し購入シグナル|直接取得診断|リンク|
|---|---|---:|---:|---|---|---:|---:|---|---|---|---|---|
|<a href="https://www.mm-vision.dk/amd-ryzen-7-9700x-processor"><img src="https://img.mm-vision.dk/images/v1/mmv/amd-9000-series-ryzen-7-02.webp" alt="AMD Ryzen 7 9700X BOX" width="92"></a>|AMD Ryzen 7 9700X BOX|89/100（用途37/40・余裕20/25・品質18/20・構成14/15）|38/100|100-100001404WOF|根拠: ゲームの応答性と8コア/16スレッドを両立し、ゲーム制作・Python分析を含む汎用本命に合う。 / 留意: UE5エンジン本体のソースフルビルドでは12～16コア級の構成より不利。大規模な並列ビルド最優先のCPUではない。|¥45,000|未取得|販売可能な直接掲載価格なし / 売切れ0・在庫不明1・取寄せ/予約0・鮮度切れ0|missing|在庫未確認|verified: exact_identity_direct_price_and_pit_verified / stock=unknown; unverified: fetch_error / stock=unknown / RemoteDisconnected / Remote end closed connection without response|[価格比較ページ](https://kakaku.com/item/K0001630332/) / [yodobashi.com 在庫不明 ¥53,110（取得 2026-10-25 01:43 JST・1分前）](https://www.yodobashi.com/product/100000001008661707/)|
|<a href="https://www.cclonline.com/90-mxbr7-a0uayz-asrock-b850m-pro-rs-wifi-matx-motherboard-for-amd-am5-cpus-476896/"><img src="https://www.cclonline.com/images/avante/B850M-Pro-RS-WiFi_box.jpg" alt="ASRock B850M Pro RS WiFi" width="92"></a>|ASRock B850M Pro RS WiFi|87/100（用途35/40・余裕22/25・品質17/20・構成13/15）|39/100|B850M Pro RS WiFi|根拠: AM5・DDR5・MicroATX・Wi-Fiを備え、選定CPUとコンパクトな空気流重視ケースの計画に合う。 / 留意: Ryzen 7 9700XのBIOS 3.12要件と出荷BIOS、メモリキットのQVL、M.2レーン共有は未確認のまま購入承認しない。|¥20,000|未取得|販売可能な直接掲載価格なし / 売切れ0・在庫不明3・取寄せ/予約0・鮮度切れ2|missing|在庫未確認|verified: exact_identity_direct_price_and_pit_verified / stock=unknown; verified: exact_identity_direct_price_and_pit_verified / stock=unknown; verified: exact_identity_direct_price_and_pit_verified / stock=unknown|[価格比較ページ](https://kakaku.com/item/K0001669878/) / [sofmap.com 在庫不明 ¥32,080（取得 2026-10-25 01:43 JST・0分前）](https://www.sofmap.com/product_detail.aspx?sku=101393495) / [pc4u.co.jp 在庫不明 ¥32,080（取得 2026-10-25 01:43 JST・1分前）](https://www.pc4u.co.jp/view/item/000000092844) / [yodobashi.com 在庫不明 ¥35,650（取得 2026-10-25 01:43 JST・1分前）](https://www.yodobashi.com/product/100000001008871801/) / [rakuten.co.jp 在庫不明（在庫情報が古い） ¥15,480（取得 2026-10-24 22:21 JST・202分前）](https://item.rakuten.co.jp/janpara/108199595-222/?iasid=07rpp_10095___35-mvmfgu5d-1c-956cacba-64f7-468e-9fa6-a95d735d515d) / [rakuten.co.jp 在庫不明（在庫情報が古い） ¥32,374（取得 2026-10-24 22:21 JST・202分前）](https://item.rakuten.co.jp/ask-direct/mb6711/?iasid=07rpp_10095___3r-mvmfgt7z-2r-b18e3cca-3991-4974-b081-50023837139b)|
|<a href="https://banin123.base.shop/items/131528972"><img src="https://baseec-img-mng.akamaized.net/images/item/origin/fe2f683b0a8212c0166b85f0c7969499.jpg?imformat=generic" alt="Corsair RM850e 2025 850W ATX 3.1 Gold" width="92"></a>|Corsair RM850e 2025 850W ATX 3.1 Gold|94/100（用途37/40・余裕24/25・品質19/20・構成14/15）|65/100|CP-9020296-JP|根拠: 850W・80 PLUS Gold・ATX 3.1の計画はRTX 5070クラスと将来の一般的な拡張に余裕を取りやすい。 / 留意: 正確な2025型番、12V-2x6ケーブルの付属、製品保証、個体の付属品を購入前に再確認する。|¥14,000|¥15,000|販売可能掲載 ¥15,000（in_stock） / 売切れ0・在庫不明0・取寄せ/予約0・鮮度切れ1|verified_retailer_listing_reference|前倒し購入価格に未到達|verified: exact_identity_direct_price_and_pit_verified / stock=in_stock; unverified: direct_price_missing_or_not_integer / stock=unknown|[価格比較ページ](https://www.dospara.co.jp/SBR83/IC519918.html) / [rakuten.co.jp 在庫不明（在庫情報が古い） ¥20,690（取得 2026-10-24 23:51 JST・112分前）](https://item.rakuten.co.jp/jism/4537694358347-44-74741-n/?variantId=4537694358347-44-74741-n)|
|<a href="https://www.dateks.lv/en/cenas/korpusi/863822-fractaldesign-pop-air-black-tg-clear-tint"><img src="https://www.dateks.lv/images/pic/2400/2400/518/1239.jpg" alt="Fractal Design Pop Air TG" width="92"></a>|Fractal Design Pop Air TG|86/100（用途35/40・余裕21/25・品質17/20・構成13/15）|64/100|FD-C-POA1A-02|根拠: エアフロー重視のケースを基準にし、長時間のゲーム・制作・分析負荷で冷却しやすい構成を狙える。 / 留意: GPU長・厚み、CPUクーラー高、ラジエーター/ファン構成など正確な部品寸法でクリアランス確認が必要。|¥12,000|¥13,180|販売可能掲載 ¥13,180（in_stock） / 売切れ0・在庫不明1・取寄せ/予約0・鮮度切れ0|verified_retailer_listing_reference|前倒し購入価格に未到達|verified: exact_identity_direct_price_and_pit_verified / stock=unknown; verified: exact_identity_direct_price_and_pit_verified / stock=in_stock|[価格比較ページ](https://www.dospara.co.jp/SBR1959/IC480986.html) / [yodobashi.com 在庫不明 ¥14,510（取得 2026-10-25 01:43 JST・0分前）](https://www.yodobashi.com/product/100000001007195271/)|
|<a href="https://shop.tsukumo.co.jp/goods/4549576190358/"><img src="https://cdn.tsukumo.co.jp/image/item/4549576190358_1.jpg" alt="Microsoft Windows 11 Home 日本語版 パッケージ版" width="92"></a>|Microsoft Windows 11 Home 日本語版 パッケージ版|79/100（用途34/40・余裕15/25・品質16/20・構成14/15）|40/100|HAJ-00094|根拠: Windows 11 Homeの正規パッケージ版を購入構成に含める計画で、一般的なゲーム・開発ツール利用に対応。 / 留意: すでに移行可能な正規ライセンスがある場合は二重購入を避ける。型番・正規販売店・ライセンス形態・有効化条件を確認する。|¥17,000|未取得|販売可能な直接掲載価格なし / 売切れ0・在庫不明1・取寄せ/予約0・鮮度切れ0|missing|在庫未確認|verified: exact_identity_direct_price_and_pit_verified / stock=unknown|[価格比較ページ](https://kakaku.com/item/K0001432816/) / [yodobashi.com 在庫不明 ¥18,380（取得 2026-10-25 01:43 JST・0分前）](https://www.yodobashi.com/product/100000001006975270/)|
|<a href="https://www.pccomponentes.com/memoria-ram-team-group-t-create-expert-ddr5-6000mhz-32gb-2x16gb-cl30-dual-amd-expo-e-intel-xmp-blanca"><img src="https://img.pccomponentes.com/articles/1086/10864724/394-team-group-t-create-expert-ddr5-6000mhz-32gb-2x16gb-cl30-dual-amd-expo-e-intel-xmp-blanca.jpg" alt="TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)" width="92"></a>|TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)|79/100（用途34/40・余裕16/25・品質16/20・構成13/15）|38/100|CTCWD532G6000HC38ADC01|根拠: 32GB・16GB×2・DDR5-6000で、購入時点の必須要件とデュアルチャネル計画を満たす。 / 留意: 大きなゲーム制作・複数ツール・データ処理を同時に行う場合の余裕は64GBより小さい。正確なQVL/EXPO安定性は要確認。|¥58,000|未取得|販売可能な直接掲載価格なし / 売切れ0・在庫不明2・取寄せ/予約0・鮮度切れ0|missing|在庫未確認|verified: exact_identity_direct_price_and_pit_verified / stock=unknown; unverified: direct_price_missing_or_not_integer / stock=unknown|[価格比較ページ](https://kakaku.com/item/K0001610896/) / [item.rakuten.co.jp 在庫不明 ¥94,024（取得 2026-10-25 01:43 JST・0分前）](https://item.rakuten.co.jp/matsukageya/mk-0chf9th1b/?variantId=mk-0chf9th1b) / [ymall.jp 在庫不明 ¥113,938（取得 2026-10-25 01:43 JST・1分前）](https://ymall.jp/store/mlymall/b0chf9th1b-20260811/)|
|<a href="https://www.cfd.co.jp/biz/product/release/ct1000p3pssd8jp.html"><img src="https://www.cfd.co.jp/webpim/product/image/c/crucial-p3-plus-m2-series/ct1000p3pssd8jp/ct1000p3pssd8jp__0100.jpg" alt="Crucial P3 Plus CT1000P3PSSD8JP 1TB" width="92"></a>|Crucial P3 Plus CT1000P3PSSD8JP 1TB|75/100（用途34/40・余裕14/25・品質13/20・構成14/15）|40/100|CT1000P3PSSD8JP|根拠: 1TB NVMeでOS・開発環境・ゲームを入れる購入時の最低容量要件を満たす。 / 留意: QLC系で長時間の大容量書込みや書込み耐久を最優先する用途にはより適した候補と比較が必要。速度表記だけで持続性能を保証しない。|¥24,000|未取得|販売可能な直接掲載価格なし / 売切れ1・在庫不明1・取寄せ/予約0・鮮度切れ1|missing|在庫未確認|unverified: fetch_error / stock=unknown / RemoteDisconnected / Remote end closed connection without response; verified: exact_identity_direct_price_and_pit_verified / stock=out_of_stock; verified: exact_identity_direct_price_and_pit_verified / stock=unknown|[価格比較ページ](https://kakaku.com/item/K0001466997/) / [kaago.com 在庫不明 ¥35,838（取得 2026-10-25 01:43 JST・0分前）](https://kaago.com/excellar/crucial%E3%80%80%E5%86%85%E8%94%B5%E5%9E%8B-M.2-SSD%E3%80%80P3-Plus-CT1000P3PSSD8JP%E3%80%801TB/?itemcode=0001000033094) / [dospara.co.jp 売切れ ¥9,300（取得 2026-10-25 01:43 JST・0分前）](https://www.dospara.co.jp/SBR1144/IC481159.html) / [yodobashi.com 在庫不明（在庫情報が古い） ¥10,210（取得 2026-10-24 23:51 JST・112分前）](https://www.yodobashi.com/product/100000001007390887/)|
|<a href="https://www.thermalright.com/product/peerless-assassin-120-se-v3/"><img src="https://thermalright.com/wp-content/uploads/2024/12/8-3-1024x1024.jpg" alt="Thermalright Peerless Assassin 120 SE V3" width="92"></a>|Thermalright Peerless Assassin 120 SE V3|91/100（用途37/40・余裕23/25・品質17/20・構成14/15）|65/100|Peerless Assassin 120 SE V3|根拠: デュアルタワー空冷でCPUの持続負荷や長いビルドに備えやすい。 / 留意: AM5金具、ケース高、メモリ干渉、実装手順、正確な商品リビジョンを確認するまで互換性は確定扱いにしない。|¥5,000|¥4,970|販売可能掲載 ¥4,970（in_stock） / 売切れ0・在庫不明0・取寄せ/予約0・鮮度切れ1|verified_retailer_listing_reference|前倒し購入価格に未到達|verified: exact_identity_direct_price_and_pit_verified / stock=in_stock|[価格比較ページ](https://www.dospara.co.jp/SBR1968/IC645423.html) / [rakuten.co.jp 在庫不明（在庫情報が古い） ¥4,980（取得 2026-10-24 23:51 JST・112分前）](https://item.rakuten.co.jp/jism/4573615591097-44-72021-n/?variantId=4573615591097-44-72021-n)|
|<a href="https://vdstore.vn/products/card-man-hinh-pny-gefocre-rtx-5070-ti-16gb-argb-epic-x-oc-triple-fan-vcg5070t16tfxxpb1-o"><img src="https://vdstore.vn/storage/main/products/vga/pny/5070-5070ti/vcg5070t16tfxxpb1-o/613a9b1e-46c8-4cc3-a3ab-61b7d9bbf92d.webp" alt="PNY GeForce RTX 5070 Ti 16GB ARGB" width="92"></a>|PNY GeForce RTX 5070 Ti 16GB ARGB|97/100（用途40/40・余裕25/25・品質18/20・構成14/15）|39/100|VCG5070T16TFXXPB1-O|根拠: 3候補中で最も高い参照ゲーム性能と16GB VRAMを狙える高性能な大穴。 / 留意: 目標構成の総額が40万円を超えるシナリオがある。購入可否は全構成・送料・周辺機器を含む実額で判定し、寸法・電源も要検証。|¥158,000|未取得|販売可能な直接掲載価格なし / 売切れ1・在庫不明0・取寄せ/予約0・鮮度切れ0|missing|在庫切れ|verified: exact_identity_direct_price_and_pit_verified / stock=out_of_stock|[価格比較ページ](https://kakaku.com/item/K0001696164/) / [dospara.co.jp 売切れ ¥219,800（取得 2026-10-25 01:43 JST・1分前）](https://www.dospara.co.jp/SBR1892/IC634895.html)|

互換性チェック:

- **PASS**: cpu_motherboard_socket — CPU socket AM5 / board socket AM5
- **REVIEW**: cpu_bios_support — ASRock support list requires BIOS 3.12; the exact board's shipped/installed BIOS is unobserved. Verify it and use BIOS Flashback/update if needed.
- **PASS**: memory_type_capacity_dual_channel — DDR type, >= 32GB, >= 2 DIMMs
- **REVIEW**: memory_qvl — Exact kit memory-teamgroup-ddr5-32gb-6000 QVL entry for ASRock B850M Pro RS WiFi: unconfirmed; DDR5/EXPO support alone is not proof of exact-kit QVL compatibility
- **PASS**: storage_capacity_interface — NVMe SSD 1000GB / minimum 1000GB
- **PASS**: motherboard_case_form_factor — Board MicroATX / case supports ATX, MicroATX, MiniITX
- **PASS**: gpu_case_clearance — GPU 300mm / case limit 405mm
- **REVIEW**: gpu_slot_thickness — GPU occupies 2.98 slots; confirm case expansion-slot, motherboard-header and cable clearance
- **PASS**: cooler_socket — AM5 mounting support declared
- **PASS**: cooler_case_clearance — Cooler 157mm / case limit 170mm
- **PASS**: psu_wattage — PSU 850W / GPU recommendation 750W
- **PASS**: gpu_power_connector — PSU ATX 3.1 native 12V-2x6 cable
- **PASS**: os_license — Windows 11 Home license included in this exact build unless a transferable existing license is verified

### 自作本命：Ryzen 7 9700X + RTX 5070 12GB

- BF目標総額（計画値）: ¥382,000。値下がり予測・実売の確定額ではない。
- 現時点の販売可能掲載: 3/9部品 / 部分合計 ¥33,150（掲載額だけ。完成価格・注文カート合計ではない）。
- 採用GPU SKU: PNY GeForce RTX 5070 12GB OC SLIM（primary_exact_sku_fallback_no_verified_in_stock_alternative）
- 採用RAM: TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)（primary_memory_fallback_no_verified_in_stock_alternative）
- 採用SSD: Crucial P3 Plus CT1000P3PSSD8JP 1TB（primary_fallback_no_verified_in_stock_alternative）
- 採用CPUクーラー: Thermalright Peerless Assassin 120 SE V3（keep_primary_if_fresh_in_stock）
- 現在の比較参考合計: 未算出。価格・型番・在庫条件を満たさない部品を0円補完しない
- 互換性: REVIEW / 判定: WAIT_FOR_COMPATIBILITY_REVIEW

部品適合点/100は用途適合40・性能/容量余裕25・品質/信頼性20・構成/拡張性15点のルーブリックから計算します。理由と制約を併記し、未入力・範囲外は未採点です。構成全体の点数や実測ベンチマークではありません。
部品購入根拠点/100は直接価格・在庫・決済総額・その部品に関係する互換性確認・保証/返品条件から動的計算します。適合点とは別で、比較サイト価格や未確認の在庫では加点しません。どちらの点数も購入許可ではありません。

|画像|部品|部品適合点/100（内訳）|部品購入根拠点/100|型番|適合評価の理由・制約|BF目標|検証済み/表示専用参考値|直接掲載価格（在庫条件未達・推定不採用）|確認状態|前倒し購入シグナル|直接取得診断|リンク|
|---|---|---:|---:|---|---|---:|---:|---|---|---|---|---|
|<a href="https://www.mm-vision.dk/amd-ryzen-7-9700x-processor"><img src="https://img.mm-vision.dk/images/v1/mmv/amd-9000-series-ryzen-7-02.webp" alt="AMD Ryzen 7 9700X BOX" width="92"></a>|AMD Ryzen 7 9700X BOX|89/100（用途37/40・余裕20/25・品質18/20・構成14/15）|38/100|100-100001404WOF|根拠: ゲームの応答性と8コア/16スレッドを両立し、ゲーム制作・Python分析を含む汎用本命に合う。 / 留意: UE5エンジン本体のソースフルビルドでは12～16コア級の構成より不利。大規模な並列ビルド最優先のCPUではない。|¥45,000|未取得|販売可能な直接掲載価格なし / 売切れ0・在庫不明1・取寄せ/予約0・鮮度切れ0|missing|在庫未確認|verified: exact_identity_direct_price_and_pit_verified / stock=unknown; unverified: fetch_error / stock=unknown / RemoteDisconnected / Remote end closed connection without response|[価格比較ページ](https://kakaku.com/item/K0001630332/) / [yodobashi.com 在庫不明 ¥53,110（取得 2026-10-25 01:43 JST・1分前）](https://www.yodobashi.com/product/100000001008661707/)|
|<a href="https://www.cclonline.com/90-mxbr7-a0uayz-asrock-b850m-pro-rs-wifi-matx-motherboard-for-amd-am5-cpus-476896/"><img src="https://www.cclonline.com/images/avante/B850M-Pro-RS-WiFi_box.jpg" alt="ASRock B850M Pro RS WiFi" width="92"></a>|ASRock B850M Pro RS WiFi|87/100（用途35/40・余裕22/25・品質17/20・構成13/15）|39/100|B850M Pro RS WiFi|根拠: AM5・DDR5・MicroATX・Wi-Fiを備え、選定CPUとコンパクトな空気流重視ケースの計画に合う。 / 留意: Ryzen 7 9700XのBIOS 3.12要件と出荷BIOS、メモリキットのQVL、M.2レーン共有は未確認のまま購入承認しない。|¥20,000|未取得|販売可能な直接掲載価格なし / 売切れ0・在庫不明3・取寄せ/予約0・鮮度切れ2|missing|在庫未確認|verified: exact_identity_direct_price_and_pit_verified / stock=unknown; verified: exact_identity_direct_price_and_pit_verified / stock=unknown; verified: exact_identity_direct_price_and_pit_verified / stock=unknown|[価格比較ページ](https://kakaku.com/item/K0001669878/) / [sofmap.com 在庫不明 ¥32,080（取得 2026-10-25 01:43 JST・0分前）](https://www.sofmap.com/product_detail.aspx?sku=101393495) / [pc4u.co.jp 在庫不明 ¥32,080（取得 2026-10-25 01:43 JST・1分前）](https://www.pc4u.co.jp/view/item/000000092844) / [yodobashi.com 在庫不明 ¥35,650（取得 2026-10-25 01:43 JST・1分前）](https://www.yodobashi.com/product/100000001008871801/) / [rakuten.co.jp 在庫不明（在庫情報が古い） ¥15,480（取得 2026-10-24 22:21 JST・202分前）](https://item.rakuten.co.jp/janpara/108199595-222/?iasid=07rpp_10095___35-mvmfgu5d-1c-956cacba-64f7-468e-9fa6-a95d735d515d) / [rakuten.co.jp 在庫不明（在庫情報が古い） ¥32,374（取得 2026-10-24 22:21 JST・202分前）](https://item.rakuten.co.jp/ask-direct/mb6711/?iasid=07rpp_10095___3r-mvmfgt7z-2r-b18e3cca-3991-4974-b081-50023837139b)|
|<a href="https://banin123.base.shop/items/131528972"><img src="https://baseec-img-mng.akamaized.net/images/item/origin/fe2f683b0a8212c0166b85f0c7969499.jpg?imformat=generic" alt="Corsair RM850e 2025 850W ATX 3.1 Gold" width="92"></a>|Corsair RM850e 2025 850W ATX 3.1 Gold|94/100（用途37/40・余裕24/25・品質19/20・構成14/15）|65/100|CP-9020296-JP|根拠: 850W・80 PLUS Gold・ATX 3.1の計画はRTX 5070クラスと将来の一般的な拡張に余裕を取りやすい。 / 留意: 正確な2025型番、12V-2x6ケーブルの付属、製品保証、個体の付属品を購入前に再確認する。|¥14,000|¥15,000|販売可能掲載 ¥15,000（in_stock） / 売切れ0・在庫不明0・取寄せ/予約0・鮮度切れ1|verified_retailer_listing_reference|前倒し購入価格に未到達|verified: exact_identity_direct_price_and_pit_verified / stock=in_stock; unverified: direct_price_missing_or_not_integer / stock=unknown|[価格比較ページ](https://www.dospara.co.jp/SBR83/IC519918.html) / [rakuten.co.jp 在庫不明（在庫情報が古い） ¥20,690（取得 2026-10-24 23:51 JST・112分前）](https://item.rakuten.co.jp/jism/4537694358347-44-74741-n/?variantId=4537694358347-44-74741-n)|
|<a href="https://www.dateks.lv/en/cenas/korpusi/863822-fractaldesign-pop-air-black-tg-clear-tint"><img src="https://www.dateks.lv/images/pic/2400/2400/518/1239.jpg" alt="Fractal Design Pop Air TG" width="92"></a>|Fractal Design Pop Air TG|86/100（用途35/40・余裕21/25・品質17/20・構成13/15）|65/100|FD-C-POA1A-02|根拠: エアフロー重視のケースを基準にし、長時間のゲーム・制作・分析負荷で冷却しやすい構成を狙える。 / 留意: GPU長・厚み、CPUクーラー高、ラジエーター/ファン構成など正確な部品寸法でクリアランス確認が必要。|¥12,000|¥13,180|販売可能掲載 ¥13,180（in_stock） / 売切れ0・在庫不明1・取寄せ/予約0・鮮度切れ0|verified_retailer_listing_reference|前倒し購入価格に未到達|verified: exact_identity_direct_price_and_pit_verified / stock=unknown; verified: exact_identity_direct_price_and_pit_verified / stock=in_stock|[価格比較ページ](https://www.dospara.co.jp/SBR1959/IC480986.html) / [yodobashi.com 在庫不明 ¥14,510（取得 2026-10-25 01:43 JST・0分前）](https://www.yodobashi.com/product/100000001007195271/)|
|<a href="https://shop.tsukumo.co.jp/goods/4549576190358/"><img src="https://cdn.tsukumo.co.jp/image/item/4549576190358_1.jpg" alt="Microsoft Windows 11 Home 日本語版 パッケージ版" width="92"></a>|Microsoft Windows 11 Home 日本語版 パッケージ版|79/100（用途34/40・余裕15/25・品質16/20・構成14/15）|40/100|HAJ-00094|根拠: Windows 11 Homeの正規パッケージ版を購入構成に含める計画で、一般的なゲーム・開発ツール利用に対応。 / 留意: すでに移行可能な正規ライセンスがある場合は二重購入を避ける。型番・正規販売店・ライセンス形態・有効化条件を確認する。|¥17,000|未取得|販売可能な直接掲載価格なし / 売切れ0・在庫不明1・取寄せ/予約0・鮮度切れ0|missing|在庫未確認|verified: exact_identity_direct_price_and_pit_verified / stock=unknown|[価格比較ページ](https://kakaku.com/item/K0001432816/) / [yodobashi.com 在庫不明 ¥18,380（取得 2026-10-25 01:43 JST・0分前）](https://www.yodobashi.com/product/100000001006975270/)|
|<a href="https://www.pccomponentes.com/memoria-ram-team-group-t-create-expert-ddr5-6000mhz-32gb-2x16gb-cl30-dual-amd-expo-e-intel-xmp-blanca"><img src="https://img.pccomponentes.com/articles/1086/10864724/394-team-group-t-create-expert-ddr5-6000mhz-32gb-2x16gb-cl30-dual-amd-expo-e-intel-xmp-blanca.jpg" alt="TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)" width="92"></a>|TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)|79/100（用途34/40・余裕16/25・品質16/20・構成13/15）|38/100|CTCWD532G6000HC38ADC01|根拠: 32GB・16GB×2・DDR5-6000で、購入時点の必須要件とデュアルチャネル計画を満たす。 / 留意: 大きなゲーム制作・複数ツール・データ処理を同時に行う場合の余裕は64GBより小さい。正確なQVL/EXPO安定性は要確認。|¥58,000|未取得|販売可能な直接掲載価格なし / 売切れ0・在庫不明2・取寄せ/予約0・鮮度切れ0|missing|在庫未確認|verified: exact_identity_direct_price_and_pit_verified / stock=unknown; unverified: direct_price_missing_or_not_integer / stock=unknown|[価格比較ページ](https://kakaku.com/item/K0001610896/) / [item.rakuten.co.jp 在庫不明 ¥94,024（取得 2026-10-25 01:43 JST・0分前）](https://item.rakuten.co.jp/matsukageya/mk-0chf9th1b/?variantId=mk-0chf9th1b) / [ymall.jp 在庫不明 ¥113,938（取得 2026-10-25 01:43 JST・1分前）](https://ymall.jp/store/mlymall/b0chf9th1b-20260811/)|
|<a href="https://www.cfd.co.jp/biz/product/release/ct1000p3pssd8jp.html"><img src="https://www.cfd.co.jp/webpim/product/image/c/crucial-p3-plus-m2-series/ct1000p3pssd8jp/ct1000p3pssd8jp__0100.jpg" alt="Crucial P3 Plus CT1000P3PSSD8JP 1TB" width="92"></a>|Crucial P3 Plus CT1000P3PSSD8JP 1TB|75/100（用途34/40・余裕14/25・品質13/20・構成14/15）|40/100|CT1000P3PSSD8JP|根拠: 1TB NVMeでOS・開発環境・ゲームを入れる購入時の最低容量要件を満たす。 / 留意: QLC系で長時間の大容量書込みや書込み耐久を最優先する用途にはより適した候補と比較が必要。速度表記だけで持続性能を保証しない。|¥24,000|未取得|販売可能な直接掲載価格なし / 売切れ1・在庫不明1・取寄せ/予約0・鮮度切れ1|missing|在庫未確認|unverified: fetch_error / stock=unknown / RemoteDisconnected / Remote end closed connection without response; verified: exact_identity_direct_price_and_pit_verified / stock=out_of_stock; verified: exact_identity_direct_price_and_pit_verified / stock=unknown|[価格比較ページ](https://kakaku.com/item/K0001466997/) / [kaago.com 在庫不明 ¥35,838（取得 2026-10-25 01:43 JST・0分前）](https://kaago.com/excellar/crucial%E3%80%80%E5%86%85%E8%94%B5%E5%9E%8B-M.2-SSD%E3%80%80P3-Plus-CT1000P3PSSD8JP%E3%80%801TB/?itemcode=0001000033094) / [dospara.co.jp 売切れ ¥9,300（取得 2026-10-25 01:43 JST・0分前）](https://www.dospara.co.jp/SBR1144/IC481159.html) / [yodobashi.com 在庫不明（在庫情報が古い） ¥10,210（取得 2026-10-24 23:51 JST・112分前）](https://www.yodobashi.com/product/100000001007390887/)|
|<a href="https://www.thermalright.com/product/peerless-assassin-120-se-v3/"><img src="https://thermalright.com/wp-content/uploads/2024/12/8-3-1024x1024.jpg" alt="Thermalright Peerless Assassin 120 SE V3" width="92"></a>|Thermalright Peerless Assassin 120 SE V3|91/100（用途37/40・余裕23/25・品質17/20・構成14/15）|65/100|Peerless Assassin 120 SE V3|根拠: デュアルタワー空冷でCPUの持続負荷や長いビルドに備えやすい。 / 留意: AM5金具、ケース高、メモリ干渉、実装手順、正確な商品リビジョンを確認するまで互換性は確定扱いにしない。|¥5,000|¥4,970|販売可能掲載 ¥4,970（in_stock） / 売切れ0・在庫不明0・取寄せ/予約0・鮮度切れ1|verified_retailer_listing_reference|前倒し購入価格に未到達|verified: exact_identity_direct_price_and_pit_verified / stock=in_stock|[価格比較ページ](https://www.dospara.co.jp/SBR1968/IC645423.html) / [rakuten.co.jp 在庫不明（在庫情報が古い） ¥4,980（取得 2026-10-24 23:51 JST・112分前）](https://item.rakuten.co.jp/jism/4573615591097-44-72021-n/?variantId=4573615591097-44-72021-n)|
|<a href="https://teknoklik.com/pny-geforce-rtx-5070-oc-12gb-dual-fan-slim-gddr7-192bit-vcg507012dfsxpb1-o-2744"><img src="https://teknoklik.com/images/product/pny/2745/pny-geforce-rtx-5070-oc-12gb-dual-fan-slim-gddr7-192bit-vcg507012dfsxpb1-o_1000x1000_NNAECGHFET.jpg" alt="PNY GeForce RTX 5070 12GB OC SLIM" width="92"></a>|PNY GeForce RTX 5070 12GB OC SLIM|89/100（用途36/40・余裕22/25・品質17/20・構成14/15）|40/100|VCG507012DFSXPB1-O|根拠: 1440pゲーム性能と12GB VRAMのバランスがよく、ゲーム制作・AI用途の優先VRAM目安も満たす。 / 留意: 参照GPU階層は対象ゲームの実測FPSではない。モデル別寸法・冷却・端子・価格・在庫の確認は別途必要。|¥138,000|未取得|販売可能な直接掲載価格なし / 売切れ1・在庫不明0・取寄せ/予約0・鮮度切れ1|missing|在庫切れ|unverified: fetch_error / stock=unknown / RuntimeError / curl_http_403; verified: exact_identity_direct_price_and_pit_verified / stock=out_of_stock; unverified: fetch_error / stock=unknown / RemoteDisconnected / Remote end closed connection without response|[価格比較ページ](https://kakaku.com/item/K0001798041/) / [sofmap.com 売切れ ¥190,800（取得 2026-10-25 01:43 JST・1分前）](https://www.sofmap.com/product_detail.aspx?eVar4=WBPT&sku=102194845) / [rakuten.co.jp 在庫不明（在庫情報が古い） ¥192,550（取得 2026-10-24 23:51 JST・113分前）](https://item.rakuten.co.jp/ask-direct/vd9404/?variantId=vd9404)|

互換性チェック:

- **PASS**: cpu_motherboard_socket — CPU socket AM5 / board socket AM5
- **REVIEW**: cpu_bios_support — ASRock support list requires BIOS 3.12; the exact board's shipped/installed BIOS is unobserved. Verify it and use BIOS Flashback/update if needed.
- **PASS**: memory_type_capacity_dual_channel — DDR type, >= 32GB, >= 2 DIMMs
- **REVIEW**: memory_qvl — Exact kit memory-teamgroup-ddr5-32gb-6000 QVL entry for ASRock B850M Pro RS WiFi: unconfirmed; DDR5/EXPO support alone is not proof of exact-kit QVL compatibility
- **PASS**: storage_capacity_interface — NVMe SSD 1000GB / minimum 1000GB
- **PASS**: motherboard_case_form_factor — Board MicroATX / case supports ATX, MicroATX, MiniITX
- **PASS**: gpu_case_clearance — GPU 290mm / case limit 405mm
- **PASS**: gpu_slot_thickness — GPU occupies 2 slots; no additional adjacent-card requirement is configured
- **PASS**: cooler_socket — AM5 mounting support declared
- **PASS**: cooler_case_clearance — Cooler 157mm / case limit 170mm
- **PASS**: psu_wattage — PSU 850W / GPU recommendation 650W
- **PASS**: gpu_power_connector — PSU ATX 3.1 native 12V-2x6 cable
- **PASS**: os_license — Windows 11 Home license included in this exact build unless a transferable existing license is verified

### 自作VRAM案：Ryzen 7 9700X + RTX 5060 Ti 16GB

- BF目標総額（計画値）: ¥364,000。値下がり予測・実売の確定額ではない。
- 現時点の販売可能掲載: 4/9部品 / 部分合計 ¥170,950（掲載額だけ。完成価格・注文カート合計ではない）。
- 採用GPU SKU: PNY GeForce RTX 5060 Ti 16GB OC（keep_primary_exact_sku_if_fresh_in_stock）
- 採用RAM: TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)（primary_memory_fallback_no_verified_in_stock_alternative）
- 採用SSD: Crucial P3 Plus CT1000P3PSSD8JP 1TB（primary_fallback_no_verified_in_stock_alternative）
- 採用CPUクーラー: Thermalright Peerless Assassin 120 SE V3（keep_primary_if_fresh_in_stock）
- 現在の比較参考合計: 未算出。価格・型番・在庫条件を満たさない部品を0円補完しない
- 互換性: REVIEW / 判定: WAIT_FOR_COMPATIBILITY_REVIEW

部品適合点/100は用途適合40・性能/容量余裕25・品質/信頼性20・構成/拡張性15点のルーブリックから計算します。理由と制約を併記し、未入力・範囲外は未採点です。構成全体の点数や実測ベンチマークではありません。
部品購入根拠点/100は直接価格・在庫・決済総額・その部品に関係する互換性確認・保証/返品条件から動的計算します。適合点とは別で、比較サイト価格や未確認の在庫では加点しません。どちらの点数も購入許可ではありません。

|画像|部品|部品適合点/100（内訳）|部品購入根拠点/100|型番|適合評価の理由・制約|BF目標|検証済み/表示専用参考値|直接掲載価格（在庫条件未達・推定不採用）|確認状態|前倒し購入シグナル|直接取得診断|リンク|
|---|---|---:|---:|---|---|---:|---:|---|---|---|---|---|
|<a href="https://www.mm-vision.dk/amd-ryzen-7-9700x-processor"><img src="https://img.mm-vision.dk/images/v1/mmv/amd-9000-series-ryzen-7-02.webp" alt="AMD Ryzen 7 9700X BOX" width="92"></a>|AMD Ryzen 7 9700X BOX|89/100（用途37/40・余裕20/25・品質18/20・構成14/15）|38/100|100-100001404WOF|根拠: ゲームの応答性と8コア/16スレッドを両立し、ゲーム制作・Python分析を含む汎用本命に合う。 / 留意: UE5エンジン本体のソースフルビルドでは12～16コア級の構成より不利。大規模な並列ビルド最優先のCPUではない。|¥45,000|未取得|販売可能な直接掲載価格なし / 売切れ0・在庫不明1・取寄せ/予約0・鮮度切れ0|missing|在庫未確認|verified: exact_identity_direct_price_and_pit_verified / stock=unknown; unverified: fetch_error / stock=unknown / RemoteDisconnected / Remote end closed connection without response|[価格比較ページ](https://kakaku.com/item/K0001630332/) / [yodobashi.com 在庫不明 ¥53,110（取得 2026-10-25 01:43 JST・1分前）](https://www.yodobashi.com/product/100000001008661707/)|
|<a href="https://www.cclonline.com/90-mxbr7-a0uayz-asrock-b850m-pro-rs-wifi-matx-motherboard-for-amd-am5-cpus-476896/"><img src="https://www.cclonline.com/images/avante/B850M-Pro-RS-WiFi_box.jpg" alt="ASRock B850M Pro RS WiFi" width="92"></a>|ASRock B850M Pro RS WiFi|87/100（用途35/40・余裕22/25・品質17/20・構成13/15）|39/100|B850M Pro RS WiFi|根拠: AM5・DDR5・MicroATX・Wi-Fiを備え、選定CPUとコンパクトな空気流重視ケースの計画に合う。 / 留意: Ryzen 7 9700XのBIOS 3.12要件と出荷BIOS、メモリキットのQVL、M.2レーン共有は未確認のまま購入承認しない。|¥20,000|未取得|販売可能な直接掲載価格なし / 売切れ0・在庫不明3・取寄せ/予約0・鮮度切れ2|missing|在庫未確認|verified: exact_identity_direct_price_and_pit_verified / stock=unknown; verified: exact_identity_direct_price_and_pit_verified / stock=unknown; verified: exact_identity_direct_price_and_pit_verified / stock=unknown|[価格比較ページ](https://kakaku.com/item/K0001669878/) / [sofmap.com 在庫不明 ¥32,080（取得 2026-10-25 01:43 JST・0分前）](https://www.sofmap.com/product_detail.aspx?sku=101393495) / [pc4u.co.jp 在庫不明 ¥32,080（取得 2026-10-25 01:43 JST・1分前）](https://www.pc4u.co.jp/view/item/000000092844) / [yodobashi.com 在庫不明 ¥35,650（取得 2026-10-25 01:43 JST・1分前）](https://www.yodobashi.com/product/100000001008871801/) / [rakuten.co.jp 在庫不明（在庫情報が古い） ¥15,480（取得 2026-10-24 22:21 JST・202分前）](https://item.rakuten.co.jp/janpara/108199595-222/?iasid=07rpp_10095___35-mvmfgu5d-1c-956cacba-64f7-468e-9fa6-a95d735d515d) / [rakuten.co.jp 在庫不明（在庫情報が古い） ¥32,374（取得 2026-10-24 22:21 JST・202分前）](https://item.rakuten.co.jp/ask-direct/mb6711/?iasid=07rpp_10095___3r-mvmfgt7z-2r-b18e3cca-3991-4974-b081-50023837139b)|
|<a href="https://banin123.base.shop/items/131528972"><img src="https://baseec-img-mng.akamaized.net/images/item/origin/fe2f683b0a8212c0166b85f0c7969499.jpg?imformat=generic" alt="Corsair RM850e 2025 850W ATX 3.1 Gold" width="92"></a>|Corsair RM850e 2025 850W ATX 3.1 Gold|94/100（用途37/40・余裕24/25・品質19/20・構成14/15）|65/100|CP-9020296-JP|根拠: 850W・80 PLUS Gold・ATX 3.1の計画はRTX 5070クラスと将来の一般的な拡張に余裕を取りやすい。 / 留意: 正確な2025型番、12V-2x6ケーブルの付属、製品保証、個体の付属品を購入前に再確認する。|¥14,000|¥15,000|販売可能掲載 ¥15,000（in_stock） / 売切れ0・在庫不明0・取寄せ/予約0・鮮度切れ1|verified_retailer_listing_reference|前倒し購入価格に未到達|verified: exact_identity_direct_price_and_pit_verified / stock=in_stock; unverified: direct_price_missing_or_not_integer / stock=unknown|[価格比較ページ](https://www.dospara.co.jp/SBR83/IC519918.html) / [rakuten.co.jp 在庫不明（在庫情報が古い） ¥20,690（取得 2026-10-24 23:51 JST・112分前）](https://item.rakuten.co.jp/jism/4537694358347-44-74741-n/?variantId=4537694358347-44-74741-n)|
|<a href="https://www.dateks.lv/en/cenas/korpusi/863822-fractaldesign-pop-air-black-tg-clear-tint"><img src="https://www.dateks.lv/images/pic/2400/2400/518/1239.jpg" alt="Fractal Design Pop Air TG" width="92"></a>|Fractal Design Pop Air TG|86/100（用途35/40・余裕21/25・品質17/20・構成13/15）|65/100|FD-C-POA1A-02|根拠: エアフロー重視のケースを基準にし、長時間のゲーム・制作・分析負荷で冷却しやすい構成を狙える。 / 留意: GPU長・厚み、CPUクーラー高、ラジエーター/ファン構成など正確な部品寸法でクリアランス確認が必要。|¥12,000|¥13,180|販売可能掲載 ¥13,180（in_stock） / 売切れ0・在庫不明1・取寄せ/予約0・鮮度切れ0|verified_retailer_listing_reference|前倒し購入価格に未到達|verified: exact_identity_direct_price_and_pit_verified / stock=unknown; verified: exact_identity_direct_price_and_pit_verified / stock=in_stock|[価格比較ページ](https://www.dospara.co.jp/SBR1959/IC480986.html) / [yodobashi.com 在庫不明 ¥14,510（取得 2026-10-25 01:43 JST・0分前）](https://www.yodobashi.com/product/100000001007195271/)|
|<a href="https://shop.tsukumo.co.jp/goods/4549576190358/"><img src="https://cdn.tsukumo.co.jp/image/item/4549576190358_1.jpg" alt="Microsoft Windows 11 Home 日本語版 パッケージ版" width="92"></a>|Microsoft Windows 11 Home 日本語版 パッケージ版|79/100（用途34/40・余裕15/25・品質16/20・構成14/15）|40/100|HAJ-00094|根拠: Windows 11 Homeの正規パッケージ版を購入構成に含める計画で、一般的なゲーム・開発ツール利用に対応。 / 留意: すでに移行可能な正規ライセンスがある場合は二重購入を避ける。型番・正規販売店・ライセンス形態・有効化条件を確認する。|¥17,000|未取得|販売可能な直接掲載価格なし / 売切れ0・在庫不明1・取寄せ/予約0・鮮度切れ0|missing|在庫未確認|verified: exact_identity_direct_price_and_pit_verified / stock=unknown|[価格比較ページ](https://kakaku.com/item/K0001432816/) / [yodobashi.com 在庫不明 ¥18,380（取得 2026-10-25 01:43 JST・0分前）](https://www.yodobashi.com/product/100000001006975270/)|
|<a href="https://www.pccomponentes.com/memoria-ram-team-group-t-create-expert-ddr5-6000mhz-32gb-2x16gb-cl30-dual-amd-expo-e-intel-xmp-blanca"><img src="https://img.pccomponentes.com/articles/1086/10864724/394-team-group-t-create-expert-ddr5-6000mhz-32gb-2x16gb-cl30-dual-amd-expo-e-intel-xmp-blanca.jpg" alt="TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)" width="92"></a>|TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)|79/100（用途34/40・余裕16/25・品質16/20・構成13/15）|38/100|CTCWD532G6000HC38ADC01|根拠: 32GB・16GB×2・DDR5-6000で、購入時点の必須要件とデュアルチャネル計画を満たす。 / 留意: 大きなゲーム制作・複数ツール・データ処理を同時に行う場合の余裕は64GBより小さい。正確なQVL/EXPO安定性は要確認。|¥58,000|未取得|販売可能な直接掲載価格なし / 売切れ0・在庫不明2・取寄せ/予約0・鮮度切れ0|missing|在庫未確認|verified: exact_identity_direct_price_and_pit_verified / stock=unknown; unverified: direct_price_missing_or_not_integer / stock=unknown|[価格比較ページ](https://kakaku.com/item/K0001610896/) / [item.rakuten.co.jp 在庫不明 ¥94,024（取得 2026-10-25 01:43 JST・0分前）](https://item.rakuten.co.jp/matsukageya/mk-0chf9th1b/?variantId=mk-0chf9th1b) / [ymall.jp 在庫不明 ¥113,938（取得 2026-10-25 01:43 JST・1分前）](https://ymall.jp/store/mlymall/b0chf9th1b-20260811/)|
|<a href="https://www.cfd.co.jp/biz/product/release/ct1000p3pssd8jp.html"><img src="https://www.cfd.co.jp/webpim/product/image/c/crucial-p3-plus-m2-series/ct1000p3pssd8jp/ct1000p3pssd8jp__0100.jpg" alt="Crucial P3 Plus CT1000P3PSSD8JP 1TB" width="92"></a>|Crucial P3 Plus CT1000P3PSSD8JP 1TB|75/100（用途34/40・余裕14/25・品質13/20・構成14/15）|40/100|CT1000P3PSSD8JP|根拠: 1TB NVMeでOS・開発環境・ゲームを入れる購入時の最低容量要件を満たす。 / 留意: QLC系で長時間の大容量書込みや書込み耐久を最優先する用途にはより適した候補と比較が必要。速度表記だけで持続性能を保証しない。|¥24,000|未取得|販売可能な直接掲載価格なし / 売切れ1・在庫不明1・取寄せ/予約0・鮮度切れ1|missing|在庫未確認|unverified: fetch_error / stock=unknown / RemoteDisconnected / Remote end closed connection without response; verified: exact_identity_direct_price_and_pit_verified / stock=out_of_stock; verified: exact_identity_direct_price_and_pit_verified / stock=unknown|[価格比較ページ](https://kakaku.com/item/K0001466997/) / [kaago.com 在庫不明 ¥35,838（取得 2026-10-25 01:43 JST・0分前）](https://kaago.com/excellar/crucial%E3%80%80%E5%86%85%E8%94%B5%E5%9E%8B-M.2-SSD%E3%80%80P3-Plus-CT1000P3PSSD8JP%E3%80%801TB/?itemcode=0001000033094) / [dospara.co.jp 売切れ ¥9,300（取得 2026-10-25 01:43 JST・0分前）](https://www.dospara.co.jp/SBR1144/IC481159.html) / [yodobashi.com 在庫不明（在庫情報が古い） ¥10,210（取得 2026-10-24 23:51 JST・112分前）](https://www.yodobashi.com/product/100000001007390887/)|
|<a href="https://www.thermalright.com/product/peerless-assassin-120-se-v3/"><img src="https://thermalright.com/wp-content/uploads/2024/12/8-3-1024x1024.jpg" alt="Thermalright Peerless Assassin 120 SE V3" width="92"></a>|Thermalright Peerless Assassin 120 SE V3|91/100（用途37/40・余裕23/25・品質17/20・構成14/15）|65/100|Peerless Assassin 120 SE V3|根拠: デュアルタワー空冷でCPUの持続負荷や長いビルドに備えやすい。 / 留意: AM5金具、ケース高、メモリ干渉、実装手順、正確な商品リビジョンを確認するまで互換性は確定扱いにしない。|¥5,000|¥4,970|販売可能掲載 ¥4,970（in_stock） / 売切れ0・在庫不明0・取寄せ/予約0・鮮度切れ1|verified_retailer_listing_reference|前倒し購入価格に未到達|verified: exact_identity_direct_price_and_pit_verified / stock=in_stock|[価格比較ページ](https://www.dospara.co.jp/SBR1968/IC645423.html) / [rakuten.co.jp 在庫不明（在庫情報が古い） ¥4,980（取得 2026-10-24 23:51 JST・112分前）](https://item.rakuten.co.jp/jism/4573615591097-44-72021-n/?variantId=4573615591097-44-72021-n)|
|<a href="https://www.idealo.es/precios/206267042/pny-geforce-rtx-5060-ti-dual-fan-oc-16gb.html"><img src="https://cdn.idealo.com/folder/Product/206267/0/206267042/s11_produktbild_max/pny-geforce-rtx-5060-ti-dual-fan-oc-16gb.jpg" alt="PNY GeForce RTX 5060 Ti 16GB OC" width="92"></a>|PNY GeForce RTX 5060 Ti 16GB OC|85/100（用途31/40・余裕24/25・品質16/20・構成14/15）|65/100|VCG5060T16DFXPB1-O|根拠: 16GB VRAMを比較的抑えた構成目標で確保でき、制作アセットや対応するローカルAIの容量面に強い。 / 留意: RTX 5070よりゲーム性能が高いとは限らない。VRAM容量だけで処理速度やモデル実行可否は決まらない。|¥120,000|¥137,800|販売可能掲載 ¥137,800（in_stock）|verified_retailer_listing_reference|前倒し購入価格に未到達|verified: exact_identity_direct_price_and_pit_verified / stock=in_stock|[価格比較ページ](https://www.dospara.co.jp/SBR1892/IC625088.html)|

互換性チェック:

- **PASS**: cpu_motherboard_socket — CPU socket AM5 / board socket AM5
- **REVIEW**: cpu_bios_support — ASRock support list requires BIOS 3.12; the exact board's shipped/installed BIOS is unobserved. Verify it and use BIOS Flashback/update if needed.
- **PASS**: memory_type_capacity_dual_channel — DDR type, >= 32GB, >= 2 DIMMs
- **REVIEW**: memory_qvl — Exact kit memory-teamgroup-ddr5-32gb-6000 QVL entry for ASRock B850M Pro RS WiFi: unconfirmed; DDR5/EXPO support alone is not proof of exact-kit QVL compatibility
- **PASS**: storage_capacity_interface — NVMe SSD 1000GB / minimum 1000GB
- **PASS**: motherboard_case_form_factor — Board MicroATX / case supports ATX, MicroATX, MiniITX
- **PASS**: gpu_case_clearance — GPU 245mm / case limit 405mm
- **PASS**: gpu_slot_thickness — GPU occupies 2 slots; no additional adjacent-card requirement is configured
- **PASS**: cooler_socket — AM5 mounting support declared
- **PASS**: cooler_case_clearance — Cooler 157mm / case limit 170mm
- **PASS**: psu_wattage — PSU 850W / GPU recommendation 600W
- **PASS**: gpu_power_connector — PSU PCIe 8-pin (6+2) cable available
- **PASS**: os_license — Windows 11 Home license included in this exact build unless a transferable existing license is verified

## 注文直前の確認

- CPUソケット／BIOS／マザーボード対応、メモリ規格・QVL・EXPO安定性。
- GPUの正確な小売型番・カード寸法・厚さ・補助電源とケース干渉。
- 電源容量・規格・付属ケーブル、クーラー高とRAM干渉、ファン配置。
- 個別店の決済価格・送料・在庫・返品期限・保証・OSライセンス。
- 比較サイト参考価格は公式BF価格ではない。公式日程・店舗価格が確認できるまで買い時判定は保留。


## 取得エラー・価格/在庫未確認の商品リンク

ここにあるリンクは、取得に失敗した商品や価格・型番・在庫の確認が完了していない商品の販売/監視ページです。**取得エラーは売り切れを意味しません**。ページがシリーズ共通の場合は、商品名・型番も照合してください。

|対象|商品|状態|取得エラー/未確認理由|確認用リンク|
|---|---|---|---|---|
|完成品PC候補|ROG Strix G16 G614FR-R9X3D5070TI|購入ページ取得エラー|RuntimeError:curl_http_403|[商品ページを開く](https://store.asus.com/jp/rog/90nr0nk7-m00cl0-rog-strix-g16-2025-g614.html)|
|完成品PC候補|ASUS TUF Gaming A16 FA608PP-R9R5070S（整備済み品・参考枠）|購入ページ取得エラー|RuntimeError:curl_http_403|[商品ページを開く](https://store.asus.com/jp/90nr0md1-m001v0-asus-tuf-gaming-a16-2026.html)|
|完成品PC候補|GALLERIA ZL9R-R57T-6-B|在庫未確認|stock_status=out_of_stock|[商品ページを開く](https://www.dospara.co.jp/TC1085/MC24569.html)|
|完成品PC候補|Lenovo Legion Pro 5i Gen 10|価格未確認|price_validation_status=reference_only|[商品ページを開く](https://www.lenovo.com/jp/ja/p/laptops/legion-laptops/legion-5-series/legion-pro-5i-gen-10-16-inch-intel/len101g0040)|
|完成品PC候補|ASUS TUF Gaming F16 FX608|購入ページ取得エラー|RuntimeError:curl_http_403|[商品ページを開く](https://store.asus.com/jp/asus-tuf-gaming-f16-fx608.html?config=90NR0NB1-M00580)|
|完成品PC候補|Acer Predator Helios Neo 16 AI PHN16-I71-N93Z57T/E|購入ページ取得エラー|RuntimeError:curl_exit_28:curl_http_000:curl: (28) Operation timed out after 18002 milliseconds with 0 bytes received|[商品ページを開く](https://store.acer.com/ja-jp/acer-phn16-i71-n93z57t-e-1)|
|完成品PC候補|GAMING A18 PRO DXJG3JPBC4JH （英語配列キーボード）|在庫未確認|stock_status=out_of_stock|[商品ページを開く](https://storejp.gigabyte.com/c/item-list/notebook/gigabyte-pc9200)|
|完成品PC候補|ROG Strix G16 G615LR-U9R5070TI|価格未確認|price_validation_status=reference_only|[商品ページを開く](https://rog.asus.com/jp/laptops/rog-strix/rog-strix-g16-2025/spec/)|
|完成品PC候補|ROG Strix G18 G815LR-U9R5070TI|価格未確認|price_validation_status=reference_only|[商品ページを開く](https://rog.asus.com/jp/laptops/rog-strix/rog-strix-g18-2025/spec/)|
|完成品PC候補|G TUNE FG-A7G7T（TGS2026出展記念モデル第2弾）|在庫未確認|stock_status=out_of_stock|[商品ページを開く](https://www.mouse-jp.co.jp/store/g/ggtune-fga7g7tg8bddw101dectgst/)|
|完成品PC候補|G TUNE DG-A7G70|在庫未確認|stock_status=unknown|[商品ページを開く](https://www.mouse-jp.co.jp/store/g/ggtune-dga7g70b5bbdw101decwa/)|
|完成品PC候補|ROG Strix G16 G614PR-R9R5070TI|購入ページ取得エラー|RuntimeError:curl_http_403|[商品ページを開く](https://store.asus.com/jp/rog/90nr0nj7-m007r0-rog-strix-g16-2025-g614.html)|
|完成品PC候補|G TUNE FG-A7G6T|在庫未確認|stock_status=unknown|[商品ページを開く](https://www.mouse-jp.co.jp/store/g/ggtune-fga7g6tg8bddw101decwa/)|
|完成品PC候補|ROG Zephyrus G16 GU606AR-U9R5070TIG32G|購入ページ取得エラー|RuntimeError:curl_http_403|[商品ページを開く](https://store.asus.com/jp/90nr0pc2-m002c0-rog-zephyrus-g16-2026.html)|
|完成品PC候補|ROG Zephyrus G14 GU405AR-U9R5070TIG|購入ページ取得エラー|RuntimeError:curl_http_403|[商品ページを開く](https://store.asus.com/jp/90nr0p94-m001d0-rog-zephyrus-g14-2026-gu405.html)|
|自作PCパーツ|AMD Ryzen 7 9700X BOX|販売可能価格/在庫未確認|Direct retailer price captured, but current stock was not confirmed.|[商品ページを開く](https://www.yodobashi.com/product/100000001008661707/)|
|自作PCパーツ|AMD Ryzen 9 9900X BOX|検索結果の参考値のみ|Search-result snippet is display-only; no direct seller price verified.|[商品ページを開く](https://kakaku.com/item/K0001630331/)|
|自作PCパーツ|AMD Ryzen 9 9950X BOX|検索結果の参考値のみ|Search-result snippet is display-only; no direct seller price verified.|[商品ページを開く](https://kakaku.com/item/K0001630330/)|
|自作PCパーツ|PNY GeForce RTX 5070 12GB OC SLIM|販売可能価格/在庫未確認|Direct retailer price captured, but current stock was not confirmed.|[商品ページを開く](https://www.sofmap.com/product_detail.aspx?eVar4=WBPT&sku=102194845)|
|自作PCパーツ|PNY GeForce RTX 5070 Ti 16GB ARGB|販売可能価格/在庫未確認|Direct retailer price captured, but current stock was not confirmed.|[商品ページを開く](https://www.dospara.co.jp/SBR1892/IC634895.html)|
|自作PCパーツ|ASRock B850M Pro RS WiFi|販売可能価格/在庫未確認|Direct retailer price captured, but current stock was not confirmed.|[商品ページを開く](https://www.sofmap.com/product_detail.aspx?sku=101393495)|
|自作PCパーツ|TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)|販売可能価格/在庫未確認|Direct retailer price captured, but current stock was not confirmed.|[商品ページを開く](https://item.rakuten.co.jp/matsukageya/mk-0chf9th1b/?variantId=mk-0chf9th1b)|
|自作PCパーツ|Crucial Pro DDR5-6000 32GB (16GBx2)|販売可能価格/在庫未確認|Direct retailer price captured, but current stock was not confirmed.|[商品ページを開く](https://www.yodobashi.com/product/100000001009315413/)|
|自作PCパーツ|Crucial P3 Plus CT1000P3PSSD8JP 1TB|販売可能価格/在庫未確認|Direct retailer price captured, but current stock was not confirmed.|[商品ページを開く](https://kaago.com/excellar/crucial%E3%80%80%E5%86%85%E8%94%B5%E5%9E%8B-M.2-SSD%E3%80%80P3-Plus-CT1000P3PSSD8JP%E3%80%801TB/?itemcode=0001000033094)|
|自作PCパーツ|Microsoft Windows 11 Home 日本語版 パッケージ版|販売可能価格/在庫未確認|Direct retailer price captured, but current stock was not confirmed.|[商品ページを開く](https://www.yodobashi.com/product/100000001006975270/)|
|自作PCパーツ|KIOXIA EXCERIA BASIC SSD-CK2.0N4B/N 2TB|検索結果の参考値のみ|Search-result snippet is display-only; no direct seller price verified.|[商品ページを開く](https://kakaku.com/item/K0001719361/)|
|自作PCパーツ|Lexar THOR RGB 2nd Gen DDR5-6000 64GB (32GBx2)|取得/照合エラー|Direct retailer price captured, but current stock was not confirmed.|[商品ページを開く](https://www.ark-pc.co.jp/i/11650134/)|
|自作PCパーツ|Corsair VENGEANCE DDR5-6000 32GB (16GBx2) CL38 EXPO/XMP|取得/照合エラー|Direct retailer price captured, but current stock was not confirmed.|[商品ページを開く](https://item.rakuten.co.jp/jism/0840440438649-44-61330-n/?variantId=0840440438649-44-61330-n)|
|自作PCパーツ|MSI SPATIUM M450 PCIe 4.0 NVMe M.2 1TB V1|取得/照合エラー|Direct retailer price captured, but current stock was not confirmed.|[商品ページを開く](https://www.yodobashi.com/product/100000001009402658/)|
|自作PCパーツ|Thermalright Assassin X 120 Refined SE|取得/照合エラー|Direct retailer price captured, but current stock was not confirmed.|[商品ページを開く](https://www.yodobashi.com/product/100000001008996814/)|
|自作PCパーツ|MSI GeForce RTX 5070 12G VENTUS 2X OC|販売可能価格/在庫未確認|Direct retailer price captured, but current stock was not confirmed.|[商品ページを開く](https://item.rakuten.co.jp/jism/4711377308229-44-73259-n/?variantId=4711377308229-44-73259-n)|
|自作PCパーツ|AMD Ryzen 7 7700 BOX (Wraith Stealth Cooler)|検索結果の参考値のみ|Search-result snippet is display-only; no direct seller price verified.|[商品ページを開く](https://kakaku.com/item/K0001711744/)|
|自作PCパーツ|ASRock B650M Pro X3D WiFi|検索結果の参考値のみ|Search-result snippet is display-only; no direct seller price verified.|[商品ページを開く](https://kakaku.com/item/K0001679617/)|
|周辺機器の個別取得元|AOC Q27G40E/11 27-inch WQHD 180Hz|販売元取得エラー|URL別取得状態=error; RuntimeError:curl_exit_28:curl_http_000:curl: (28) Operation timed out after 18002 milliseconds with 0 bytes received|[商品ページを開く](https://www.biccamera.com/bc/item/14369301/)|
|周辺機器の個別取得元|Logicool G213r|販売元取得エラー|URL別取得状態=error; RuntimeError:curl_exit_28:curl_http_000:curl: (28) Operation timed out after 18002 milliseconds with 0 bytes received|[商品ページを開く](https://www.biccamera.com/bc/item/9242996/)|
|周辺機器の個別取得元|Logicool G213r|販売元の価格未確認|URL別取得状態=price_unverified; missing_or_implausible_price|[商品ページを開く](https://item.rakuten.co.jp/logicool/g213r/)|
|周辺機器の個別取得元|Logicool G304|販売元取得エラー|URL別取得状態=error; RuntimeError:curl_exit_28:curl_http_000:curl: (28) Operation timed out after 18002 milliseconds with 0 bytes received|[商品ページを開く](https://www.biccamera.com/bc/item/6566291/)|
|周辺機器の個別取得元|SteelSeries QcK Large Black 450x400mm (model 63003)|販売元取得エラー|URL別取得状態=error; RuntimeError:curl_exit_28:curl_http_000:curl: (28) Operation timed out after 18002 milliseconds with 0 bytes received|[商品ページを開く](https://www.biccamera.com/bc/item/1570130/)|
|周辺機器の個別取得元|ELECOM ECCAC-DP1420BK DisplayPort 1.4 cable 2m|販売元の価格未確認|URL別取得状態=price_unverified; missing_or_implausible_price|[商品ページを開く](https://www.elecom.co.jp/products/ECCAC-DP1420BK.html)|
|周辺機器|ELECOM ECCAC-DP1420BK DisplayPort 1.4 cable 2m|取得/価格解析エラー|https://www.elecom.co.jp/products/ECCAC-DP1420BK.html: missing_or_implausible_price|[商品ページを開く](https://www.elecom.co.jp/products/ECCAC-DP1420BK.html)|
|周辺機器の個別取得元|Sanwa Supply KC-DP1420 VESA-certified DisplayPort 1.4 cable 2m|販売元の価格未確認|URL別取得状態=price_unverified; missing_or_implausible_price|[商品ページを開く](https://www.sanwa.co.jp/product/syohin?code=KC-DP1420)|
|周辺機器|Sanwa Supply KC-DP1420 VESA-certified DisplayPort 1.4 cable 2m|取得/価格解析エラー|https://www.sanwa.co.jp/product/syohin?code=KC-DP1420: missing_or_implausible_price|[商品ページを開く](https://www.sanwa.co.jp/product/syohin?code=KC-DP1420)|
|周辺機器の個別取得元|Logicool G413 TKL SE tenkeyless tactile mechanical keyboard|販売元取得エラー|URL別取得状態=error; RuntimeError:curl_exit_28:curl_http_000:curl: (28) Operation timed out after 18002 milliseconds with 0 bytes received|[商品ページを開く](https://www.biccamera.com/bc/item/10326363/)|
|周辺機器の個別取得元|Logicool G413 SE full-size tactile mechanical keyboard|販売元の価格未確認|URL別取得状態=price_unverified; missing_or_implausible_price|[商品ページを開く](https://www.yodobashi.com/product/100000001007258184/)|
|周辺機器の個別取得元|Logicool G413 SE full-size tactile mechanical keyboard|販売元取得エラー|URL別取得状態=error; RuntimeError:curl_exit_28:curl_http_000:curl: (28) Operation timed out after 18002 milliseconds with 0 bytes received|[商品ページを開く](https://www.biccamera.com/bc/item/10326362/)|
|周辺機器|Logicool G413 SE full-size tactile mechanical keyboard|取得/価格解析エラー|https://www.yodobashi.com/product/100000001007258184/: missing_or_implausible_price; https://www.biccamera.com/bc/item/10326362/: RuntimeError:curl_exit_28:curl_http_000:curl: (28) Operation|[商品ページを開く](https://www.biccamera.com/bc/item/10326362/)|
|周辺機器の個別取得元|MSI MAG 275QF 27-inch WQHD 180Hz Rapid IPS|販売元の価格未確認|URL別取得状態=price_unverified; missing_or_implausible_price|[商品ページを開く](https://kakaku.com/item/K0001690691/)|
|周辺機器|MSI MAG 275QF 27-inch WQHD 180Hz Rapid IPS|取得/価格解析エラー|https://kakaku.com/item/K0001690691/: missing_or_implausible_price|[商品ページを開く](https://kakaku.com/item/K0001690691/)|
|周辺機器の個別取得元|LG UltraGear 27GS75Q-B 27-inch WQHD IPS 180Hz|販売元の価格未確認|URL別取得状態=price_unverified; missing_or_implausible_price|[商品ページを開く](https://www.lg.com/jp/monitors/gaming-monitors/27gs75q-b/)|
|周辺機器|LG UltraGear 27GS75Q-B 27-inch WQHD IPS 180Hz|取得/価格解析エラー|https://www.lg.com/jp/monitors/gaming-monitors/27gs75q-b/: missing_or_implausible_price|[商品ページを開く](https://www.lg.com/jp/monitors/gaming-monitors/27gs75q-b/)|
|周辺機器の個別取得元|Logicool G203 LIGHTSYNC wired gaming mouse (black)|販売元取得エラー|URL別取得状態=error; RuntimeError:curl_exit_28:curl_http_000:curl: (28) Operation timed out after 18002 milliseconds with 0 bytes received|[商品ページを開く](https://www.biccamera.com/bc/item/8019882/)|
|周辺機器の個別取得元|Logicool G304 X SUPERLIGHT wireless gaming mouse|販売元取得エラー|URL別取得状態=error; RuntimeError:curl_exit_28:curl_http_000:curl: (28) Operation timed out after 18002 milliseconds with 0 bytes received|[商品ページを開く](https://www.biccamera.com/bc/item/15216264/)|
|周辺機器|Logicool G304 X SUPERLIGHT wireless gaming mouse|取得/価格解析エラー|https://www.biccamera.com/bc/item/15216264/: RuntimeError:curl_exit_28:curl_http_000:curl: (28) Operation timed out after 18002 milliseconds with 0 bytes received|[商品ページを開く](https://www.biccamera.com/bc/item/15216264/)|
|周辺機器の個別取得元|Razer Gigantus V2 Large 450x400mm cloth gaming mouse mat|販売元の価格未確認|URL別取得状態=price_unverified; missing_or_implausible_price|[商品ページを開く](https://www.razer.com/jp-jp/gaming-mouse-mats/Razer-Gigantus-V2/RZ02-03330300-R3M1)|
|周辺機器|Razer Gigantus V2 Large 450x400mm cloth gaming mouse mat|取得/価格解析エラー|https://www.razer.com/jp-jp/gaming-mouse-mats/Razer-Gigantus-V2/RZ02-03330300-R3M1: missing_or_implausible_price|[商品ページを開く](https://www.razer.com/jp-jp/gaming-mouse-mats/Razer-Gigantus-V2/RZ02-03330300-R3M1)|
|周辺機器の個別取得元|Logicool G640 Large cloth gaming mousepad|販売元の価格未確認|URL別取得状態=price_unverified; missing_or_implausible_price|[商品ページを開く](https://gaming.logicool.co.jp/ja-jp/shop/p/g640-cloth-gaming-mouse-pad)|
|周辺機器|Logicool G640 Large cloth gaming mousepad|取得/価格解析エラー|https://gaming.logicool.co.jp/ja-jp/shop/p/g640-cloth-gaming-mouse-pad: missing_or_implausible_price|[商品ページを開く](https://gaming.logicool.co.jp/ja-jp/shop/p/g640-cloth-gaming-mouse-pad)|

未確認項目は在庫切れ・価格ゼロとみなさず、リンク先で直接確認するまで購入可否の根拠にしません。