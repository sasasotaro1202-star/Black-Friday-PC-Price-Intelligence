# 自作PCパーツ構成・価格監視

更新: 2026-10-17T20:59:47+09:00
予算: PC本体 ¥395,000 / 周辺機器 ¥35,000 / 総額 ¥400,000

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
勉強・調査: school/study work、reading and summarizing source documents、research、writing and presentations、browser with many tabs、video lessons and note-taking
データ分析・自動化・AI: Python data analysis、large datasets and simulations、sports prediction systems、stock/securities prediction、BTC prediction、GitHub Actions and local tests、AI-assisted workflows、local AI models when feasible
同時利用想定: IDE/ゲームエンジン/Python/テスト/資料閲覧/ブラウザー/AIツール。CPU・RAM・VRAM・SSD・冷却を用途別に確認し、すべての分析処理がGPUで速くなるとは仮定しません。

**メモリ選択:** TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)
選定方法: primary_memory_fallback_no_verified_in_stock_alternative
価格比較では、型番一致・鮮度・PIT条件を満たす市場参考値がある候補のうち、価格が最も低いものを優先します。どの候補にも信頼できる参考値がない場合は、設定ファイルで指定した既定メモリを計画上の候補として維持します。市場参考値は決済価格ではなく、購入許可も意味しません。

- Crucial Pro DDR5-6000 32GB (16GBx2) / BF目標 ¥60,000 / 比較参考 未検証 / 状態 missing / [商品ページ](https://kakaku.com/item/K0001633533/)
- TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2) / BF目標 ¥58,000 / 比較参考 未検証 / 状態 missing / [商品ページ](https://kakaku.com/item/K0001610896/)
- Lexar THOR RGB 2nd Gen DDR5-6000 64GB (32GBx2) / BF目標 ¥100,000 / 比較参考 未検証 / 状態 missing / [商品ページ](https://www.ark-pc.co.jp/i/11650134/)
- Corsair VENGEANCE DDR5-6000 32GB (16GBx2) CL38 EXPO/XMP / BF目標 ¥59,000 / 比較参考 未検証 / 状態 missing / [商品ページ](https://www.corsair.com/jp/ja/p/memory/cmk32gx5m2d6000z38/vengeance-32gb-2-x-16gb-ddr5-dram-up-to-6000mt-s-cl38-amd-expo-%26-intel-xmp-memory-kit-gray-cmk32gx5m2d6000z38)

## 現時点の販売店掲載価格・在庫（BF目標とは別集計）

以下は、商品型番・取得時刻が検証できた直接販売店ページのうち、在庫あり／在庫少と明示された掲載価格だけの部分小計です。注文カートの最終価格ではなく、在庫不明・売り切れ・未取得の部品は合計に埋めません。必須部品すべてに販売可能な掲載価格がそろわない構成は、PC本体価格を算定できません。

|構成|販売可能掲載価格が確認できた部品|部品数カバー率|確認済み掲載価格の部分小計|在庫切れ掲載（売り切れ）|在庫不明掲載|鮮度切れ掲載|販売可能価格が未確認の部品|
|---|---|---:|---:|---:|---:|---:|---|
|自作大穴：Ryzen 7 9700X + RTX 5070 Ti 16GB|5/9|55.6%|¥305,040|5|4|0|ASRock B850M Pro RS WiFi、TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)、Crucial P3 Plus CT1000P3PSSD8JP 1TB、Thermalright Peerless Assassin 120 SE V3|
|自作本命：Ryzen 7 9700X + RTX 5070 12GB|4/9|44.4%|¥95,240|6|5|0|ASRock B850M Pro RS WiFi、TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)、Crucial P3 Plus CT1000P3PSSD8JP 1TB、Thermalright Peerless Assassin 120 SE V3、PNY GeForce RTX 5070 12GB OC SLIM|
|自作VRAM案：Ryzen 7 9700X + RTX 5060 Ti 16GB|5/9|55.6%|¥225,040|5|4|0|ASRock B850M Pro RS WiFi、TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)、Crucial P3 Plus CT1000P3PSSD8JP 1TB、Thermalright Peerless Assassin 120 SE V3|

**重要:** 「確認済み掲載価格の部分小計」は全構成の現在価格ではありません。部品ごとの価格時刻・売り切れ状態は下の部品表を確認してください。価格や在庫を取得できないことを「売り切れ」とは推定しません。

## 100点方式の構成スコア（BF目標構成ベース）

構成点は用途適性・目標総額ベースの相対価格効率・互換性で採点。ゲーム点は[Tom's Hardware GPU Benchmarks Hierarchy 2026](https://www.tomshardware.com/reviews/gpu-hierarchy,4388.html)の1440p Ultraラスタライズ値を25点満点に正規化した代理指標で、対象ゲームの実測FPSではありません。参照表の最終更新日は2026-06-24です。GPU参照FPSも各構成に対応させて表示します。
購入根拠充足度は直接価格・型番・取得時刻・販売可能在庫・検証済み決済総額・互換性を別計算し、購入許可とは切り離します。

|順位|構成|GPU参照FPS (1440p Ultra)|総合点/100|ゲーム/25|制作/20|分析・AI/20|勉強・同時利用/10|価格効率/15|互換性/10|購入根拠充足度/100|直接価格・在庫・決済確認率|市場参考値|
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
|1|自作大穴：Ryzen 7 9700X + RTX 5070 Ti 16GB|116.8|86.0|25.0|16.7|12.5|8.0|15.0|8.8|61.5|価格100.0%・在庫55.6%・決済0.0%|5/9|
|2|自作本命：Ryzen 7 9700X + RTX 5070 12GB|96.4|77.5|20.6|14.7|11.2|8.0|13.8|9.2|59.5|価格100.0%・在庫44.4%・決済0.0%|4/9|
|3|自作VRAM案：Ryzen 7 9700X + RTX 5060 Ti 16GB|73.4|76.2|15.7|16.7|12.5|8.0|14.1|9.2|62.3|価格100.0%・在庫55.6%・決済0.0%|5/9|

## 目標総額と購入ゲート

|順位|構成|部品目標小計|PC本体目標総額|周辺機器込み目標|目標残額|比較参考合計|互換性|判定|
|---:|---|---:|---:|---:|---:|---:|---|---|
|1|自作大穴：Ryzen 7 9700X + RTX 5070 Ti 16GB|¥353,000|¥362,000|¥402,000|¥-2,000|未確認|REVIEW|OVER_BUDGET_TARGET|
|2|自作本命：Ryzen 7 9700X + RTX 5070 12GB|¥333,000|¥342,000|¥382,000|¥18,000|未確認|REVIEW|WAIT_FOR_COMPATIBILITY_REVIEW|
|3|自作VRAM案：Ryzen 7 9700X + RTX 5060 Ti 16GB|¥315,000|¥324,000|¥364,000|¥36,000|未確認|REVIEW|WAIT_FOR_COMPATIBILITY_REVIEW|

## 現在の在庫・売り切れリスク（購入可能総額ではない）

この表は最新スナップショットの、型番一致した販売店掲載の観測です。価格・在庫は注文時に変わる可能性があります。売り切れ価格は販売可能額に加算せず、取得失敗・在庫不明は売り切れと断定しません。

|構成|販売可能掲載を確認|うち在庫少|監視先すべて売切れ|在庫未確認/未取得|販売可能掲載の部分合計|完成総額|
|---|---:|---:|---:|---:|---:|---|
|自作大穴：Ryzen 7 9700X + RTX 5070 Ti 16GB|5/9|0|2|2|¥305,040（掲載価格のみ）|未算出（全パーツ・送料・決済条件の確認が必要）|

- 自作大穴：Ryzen 7 9700X + RTX 5070 Ti 16GB — 在庫少: なし / 監視先すべて売切れ: Crucial P3 Plus CT1000P3PSSD8JP 1TB、Thermalright Peerless Assassin 120 SE V3 / 在庫未確認・未取得: ASRock B850M Pro RS WiFi、TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)
- 販売可能掲載の部分合計は5部品分。完成PC価格でも、送料・一括決済済み金額でもありません。
|自作本命：Ryzen 7 9700X + RTX 5070 12GB|4/9|0|2|3|¥95,240（掲載価格のみ）|未算出（全パーツ・送料・決済条件の確認が必要）|

- 自作本命：Ryzen 7 9700X + RTX 5070 12GB — 在庫少: なし / 監視先すべて売切れ: Crucial P3 Plus CT1000P3PSSD8JP 1TB、Thermalright Peerless Assassin 120 SE V3 / 在庫未確認・未取得: ASRock B850M Pro RS WiFi、TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)、PNY GeForce RTX 5070 12GB OC SLIM
- 販売可能掲載の部分合計は4部品分。完成PC価格でも、送料・一括決済済み金額でもありません。
|自作VRAM案：Ryzen 7 9700X + RTX 5060 Ti 16GB|5/9|0|2|2|¥225,040（掲載価格のみ）|未算出（全パーツ・送料・決済条件の確認が必要）|

- 自作VRAM案：Ryzen 7 9700X + RTX 5060 Ti 16GB — 在庫少: なし / 監視先すべて売切れ: Crucial P3 Plus CT1000P3PSSD8JP 1TB、Thermalright Peerless Assassin 120 SE V3 / 在庫未確認・未取得: ASRock B850M Pro RS WiFi、TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)
- 販売可能掲載の部分合計は5部品分。完成PC価格でも、送料・一括決済済み金額でもありません。

## 売り切れ時の代替候補（自動注文なし・型番別に再検証）

代替SKUへの切り替えは、同じ規格/クラスか、正確な型番、最新の直接価格、販売可能在庫、互換性が検証できた場合だけ計画上で行います。低在庫は売り切れリスクとして別途示し、在庫不明を在庫ありと扱いません。

|カテゴリ|候補|目標価格|販売可能な直接掲載|在庫信号|比較サイト参考（在庫・購入可否の根拠ではない）|選定ルール|商品ページ|
|---|---|---:|---:|---|---|---|---|
|メモリ|Crucial Pro DDR5-6000 32GB (16GBx2)|¥60,000|販売可能価格なし|在庫未確認|未検証/未取得|検証済み在庫あり候補の価格比較|[商品ページ](https://kakaku.com/item/K0001633533/)|
|メモリ|TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)（選定中）|¥58,000|販売可能価格なし|在庫未確認|未検証/未取得|検証済み在庫あり候補の価格比較|[商品ページ](https://kakaku.com/item/K0001610896/)|
|メモリ|Lexar THOR RGB 2nd Gen DDR5-6000 64GB (32GBx2)|¥100,000|販売可能価格なし|在庫未確認|未検証/未取得|検証済み在庫あり候補の価格比較|[商品ページ](https://www.ark-pc.co.jp/i/11650134/)|
|メモリ|Corsair VENGEANCE DDR5-6000 32GB (16GBx2) CL38 EXPO/XMP|¥59,000|販売可能価格なし|在庫未確認|未検証/未取得|検証済み在庫あり候補の価格比較|[商品ページ](https://www.corsair.com/jp/ja/p/memory/cmk32gx5m2d6000z38/vengeance-32gb-2-x-16gb-ddr5-dram-up-to-6000mt-s-cl38-amd-expo-%26-intel-xmp-memory-kit-gray-cmk32gx5m2d6000z38)|
|SSD|Crucial P3 Plus CT1000P3PSSD8JP 1TB（選定中）|¥24,000|販売可能価格なし|売切れ|未検証/未取得|優先SSDが買えなければ、在庫確認済みの1TB NVMeへ切替|[商品ページ](https://kakaku.com/item/K0001466997/)|
|SSD|MSI SPATIUM M450 PCIe 4.0 NVMe M.2 1TB V1|¥25,000|販売可能価格なし|在庫未確認|未検証/未取得|優先SSDが買えなければ、在庫確認済みの1TB NVMeへ切替|[商品ページ](https://www.yodobashi.com/product/100000001009402658/)|
|CPUクーラー|Thermalright Peerless Assassin 120 SE V3（選定中）|¥5,000|販売可能価格なし|売切れ|未検証/未取得|優先クーラーが買えなければ、互換性を確認した代替へ切替|[商品ページ](https://kakaku.com/item/K0001789043/)|
|CPUクーラー|Thermalright Assassin X 120 Refined SE|¥2,500|販売可能価格なし|在庫未確認|未検証/未取得|優先クーラーが買えなければ、互換性を確認した代替へ切替|[商品ページ](https://www.yodobashi.com/product/100000001008996814/)|
|GPU代替|MSI GeForce RTX 5070 12G VENTUS 2X OC|¥138,000|販売可能価格なし|在庫未確認|未検証/未取得|同じGPUクラスの別SKU。寸法・端子・冷却を再確認|[商品ページ](https://shop.tsukumo.co.jp/goods/4711377308229/)|

## 構成別の詳細


### 自作大穴：Ryzen 7 9700X + RTX 5070 Ti 16GB

- BF目標総額（計画値）: ¥402,000。値下がり予測・実売の確定額ではない。
- 現時点の販売可能掲載: 5/9部品 / 部分合計 ¥305,040（掲載額だけ。完成価格・注文カート合計ではない）。
- 採用GPU SKU: PNY GeForce RTX 5070 Ti 16GB ARGB（keep_primary_exact_sku_if_fresh_in_stock）
- 採用RAM: TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)（primary_memory_fallback_no_verified_in_stock_alternative）
- 採用SSD: Crucial P3 Plus CT1000P3PSSD8JP 1TB（primary_fallback_no_verified_in_stock_alternative）
- 採用CPUクーラー: Thermalright Peerless Assassin 120 SE V3（primary_fallback_no_verified_in_stock_alternative）
- 現在の比較参考合計: 未算出。価格・型番・在庫条件を満たさない部品を0円補完しない
- 互換性: REVIEW / 判定: OVER_BUDGET_TARGET

|画像|部品|型番|BF目標|検証済み/表示専用参考値|直接掲載価格（在庫条件未達・推定不採用）|確認状態|前倒し購入シグナル|直接取得診断|リンク|
|---|---|---|---:|---:|---|---|---|---|---|---|
|<a href="https://www.mm-vision.dk/amd-ryzen-7-9700x-processor"><img src="https://img.mm-vision.dk/images/v1/mmv/amd-9000-series-ryzen-7-02.webp" alt="AMD Ryzen 7 9700X BOX" width="92"></a>|AMD Ryzen 7 9700X BOX|100-100001404WOF|¥45,000|¥47,800|販売可能掲載 ¥47,800（in_stock） / 売切れ0・在庫不明1・取寄せ/予約0・鮮度切れ0|verified_retailer_listing_reference|前倒し購入価格に未到達|verified: exact_identity_direct_price_and_pit_verified / stock=unknown; verified: exact_identity_direct_price_and_pit_verified / stock=in_stock|[価格比較ページ](https://shop.tsukumo.co.jp/goods/0730143315593/) / [100-100001404WOF 在庫不明 ¥53,110](https://www.yodobashi.com/product/100000001008661707/)|
|<a href="https://www.cclonline.com/90-mxbr7-a0uayz-asrock-b850m-pro-rs-wifi-matx-motherboard-for-amd-am5-cpus-476896/"><img src="https://www.cclonline.com/images/avante/B850M-Pro-RS-WiFi_box.jpg" alt="ASRock B850M Pro RS WiFi" width="92"></a>|ASRock B850M Pro RS WiFi|B850M Pro RS WiFi|¥20,000|未取得|販売可能な直接掲載価格なし / 売切れ1・在庫不明2・取寄せ/予約0・鮮度切れ0|missing|在庫未確認|verified: exact_identity_direct_price_and_pit_verified / stock=unknown; verified: exact_identity_direct_price_and_pit_verified / stock=out_of_stock; verified: exact_identity_direct_price_and_pit_verified / stock=unknown|[価格比較ページ](https://kakaku.com/item/K0001669878/) / [B850M Pro RS WiFi 在庫不明 ¥26,990](https://www.yodobashi.com/product/100000001008871801/) / [マザーボード(Socket AM5)   B850M Pro RS W 在庫不明 ¥32,080](https://www.sofmap.com/product_detail.aspx?sku=101393495) / [B850M Pro RS WiFi 売切れ ¥32,090](https://www.pc4u.co.jp/view/item/000000092844)|
|<a href="https://banin123.base.shop/items/131528972"><img src="https://baseec-img-mng.akamaized.net/images/item/origin/fe2f683b0a8212c0166b85f0c7969499.jpg?imformat=generic" alt="Corsair RM850e 2025 850W ATX 3.1 Gold" width="92"></a>|Corsair RM850e 2025 850W ATX 3.1 Gold|CP-9020296-JP|¥14,000|¥14,980|販売可能掲載 ¥14,980（in_stock）|verified_retailer_listing_reference|前倒し購入価格に未到達|verified: exact_identity_direct_price_and_pit_verified / stock=in_stock; unverified: direct_price_missing_or_not_integer / stock=unknown|[価格比較ページ](https://www.dospara.co.jp/SBR83/IC519918.html)|
|<a href="https://www.dateks.lv/en/cenas/korpusi/863822-fractaldesign-pop-air-black-tg-clear-tint"><img src="https://www.dateks.lv/images/pic/2400/2400/518/1239.jpg" alt="Fractal Design Pop Air TG" width="92"></a>|Fractal Design Pop Air TG|FD-C-POA1A-02|¥12,000|¥13,180|販売可能掲載 ¥13,180（in_stock） / 売切れ0・在庫不明0・取寄せ/予約1・鮮度切れ0|verified_retailer_listing_reference|前倒し購入価格に未到達|verified: exact_identity_direct_price_and_pit_verified / stock=preorder_or_backorder; verified: exact_identity_direct_price_and_pit_verified / stock=in_stock|[価格比較ページ](https://www.dospara.co.jp/SBR1959/IC480986.html) / [FD-C-POA1A-02 取寄せ/予約 ¥14,510](https://www.yodobashi.com/product/100000001007195271/)|
|<a href="https://shop.tsukumo.co.jp/goods/4549576190358/"><img src="https://cdn.tsukumo.co.jp/image/item/4549576190358_1.jpg" alt="Microsoft Windows 11 Home 日本語版 パッケージ版" width="92"></a>|Microsoft Windows 11 Home 日本語版 パッケージ版|HAJ-00094|¥17,000|¥19,280|販売可能掲載 ¥19,280（in_stock）|verified_retailer_listing_reference|前倒し購入価格に未到達|verified: exact_identity_direct_price_and_pit_verified / stock=in_stock|[価格比較ページ](https://www.yodobashi.com/product/100000001006975270/)|
|<a href="https://www.pccomponentes.com/memoria-ram-team-group-t-create-expert-ddr5-6000mhz-32gb-2x16gb-cl30-dual-amd-expo-e-intel-xmp-blanca"><img src="https://img.pccomponentes.com/articles/1086/10864724/394-team-group-t-create-expert-ddr5-6000mhz-32gb-2x16gb-cl30-dual-amd-expo-e-intel-xmp-blanca.jpg" alt="TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)" width="92"></a>|TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)|CTCWD532G6000HC38ADC01|¥58,000|未取得|販売可能な直接掲載価格なし / 売切れ0・在庫不明1・取寄せ/予約0・鮮度切れ0|missing|在庫未確認|verified: exact_identity_direct_price_and_pit_verified / stock=unknown; unverified: direct_price_missing_or_not_integer / stock=unknown|[価格比較ページ](https://kakaku.com/item/K0001610896/) / [TEAMGROUP (旧称 Team) T-CREATE EXPERT 在庫不明 ¥113,938](https://ymall.jp/store/mlymall/b0chf9th1b-20260811/)|
|<a href="https://www.cfd.co.jp/biz/product/release/ct1000p3pssd8jp.html"><img src="https://www.cfd.co.jp/webpim/product/image/c/crucial-p3-plus-m2-series/ct1000p3pssd8jp/ct1000p3pssd8jp__0100.jpg" alt="Crucial P3 Plus CT1000P3PSSD8JP 1TB" width="92"></a>|Crucial P3 Plus CT1000P3PSSD8JP 1TB|CT1000P3PSSD8JP|¥24,000|¥35,500（検索スニペット参考のみ）|販売可能な直接掲載価格なし / 売切れ3・在庫不明0・取寄せ/予約0・鮮度切れ0|search_snippet_reference_only|在庫切れ|verified: exact_identity_direct_price_and_pit_verified / stock=out_of_stock; verified: exact_identity_direct_price_and_pit_verified / stock=out_of_stock; verified: exact_identity_direct_price_and_pit_verified / stock=out_of_stock|[価格比較ページ](https://kakaku.com/item/K0001466997/) / [Crucial  P3 Plus CT1000P3PSSD8JP (M 売切れ ¥9,300](https://www.dospara.co.jp/SBR1144/IC481159.html) / [P3 Plus CT1000P3PSSD8JP [M.2 NVMe 内 売切れ ¥10,450](https://shop.tsukumo.co.jp/goods/0649528918970/) / [https://kaago.com/excellar/crucial% 売切れ ¥32,769](https://kaago.com/excellar/crucial%E3%80%80%E5%86%85%E8%94%B5%E5%9E%8B-M.2-SSD%E3%80%80P3-Plus-CT1000P3PSSD8JP%E3%80%801TB/?itemcode=0001000033094) / [検索ページ参考元](https://search.kakaku.com/Crucial%20P3%20Plus%20CT1000P3PSSD8JP%201TB/)|
|<a href="https://www.thermalright.com/product/peerless-assassin-120-se-v3/"><img src="https://thermalright.com/wp-content/uploads/2024/12/8-3-1024x1024.jpg" alt="Thermalright Peerless Assassin 120 SE V3" width="92"></a>|Thermalright Peerless Assassin 120 SE V3|Peerless Assassin 120 SE V3|¥5,000|¥4,980（検索スニペット参考のみ）|販売可能な直接掲載価格なし / 売切れ1・在庫不明0・取寄せ/予約0・鮮度切れ0|search_snippet_reference_only|在庫切れ|verified: exact_identity_direct_price_and_pit_verified / stock=out_of_stock|[価格比較ページ](https://kakaku.com/item/K0001789043/) / [Thermalright  Peerless Assassin 120 売切れ ¥4,980](https://www.dospara.co.jp/SBR1968/IC645423.html) / [検索ページ参考元](https://search.kakaku.com/Thermalright%20Peerless%20Assassin%20120%20SE%20V3/)|
|<a href="https://vdstore.vn/products/card-man-hinh-pny-gefocre-rtx-5070-ti-16gb-argb-epic-x-oc-triple-fan-vcg5070t16tfxxpb1-o"><img src="https://vdstore.vn/storage/main/products/vga/pny/5070-5070ti/vcg5070t16tfxxpb1-o/613a9b1e-46c8-4cc3-a3ab-61b7d9bbf92d.webp" alt="PNY GeForce RTX 5070 Ti 16GB ARGB" width="92"></a>|PNY GeForce RTX 5070 Ti 16GB ARGB|VCG5070T16TFXXPB1-O|¥158,000|¥209,800|販売可能掲載 ¥209,800（in_stock）|verified_retailer_listing_reference|前倒し購入価格に未到達|verified: exact_identity_direct_price_and_pit_verified / stock=in_stock|[価格比較ページ](https://www.dospara.co.jp/SBR1892/IC634895.html)|

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
- **PASS**: os_license — Windows 11 Home license budgeted unless an existing transferable license is confirmed

### 自作本命：Ryzen 7 9700X + RTX 5070 12GB

- BF目標総額（計画値）: ¥382,000。値下がり予測・実売の確定額ではない。
- 現時点の販売可能掲載: 4/9部品 / 部分合計 ¥95,240（掲載額だけ。完成価格・注文カート合計ではない）。
- 採用GPU SKU: PNY GeForce RTX 5070 12GB OC SLIM（primary_exact_sku_fallback_no_verified_in_stock_alternative）
- 採用RAM: TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)（primary_memory_fallback_no_verified_in_stock_alternative）
- 採用SSD: Crucial P3 Plus CT1000P3PSSD8JP 1TB（primary_fallback_no_verified_in_stock_alternative）
- 採用CPUクーラー: Thermalright Peerless Assassin 120 SE V3（primary_fallback_no_verified_in_stock_alternative）
- 現在の比較参考合計: 未算出。価格・型番・在庫条件を満たさない部品を0円補完しない
- 互換性: REVIEW / 判定: WAIT_FOR_COMPATIBILITY_REVIEW

|画像|部品|型番|BF目標|検証済み/表示専用参考値|直接掲載価格（在庫条件未達・推定不採用）|確認状態|前倒し購入シグナル|直接取得診断|リンク|
|---|---|---|---:|---:|---|---|---|---|---|---|
|<a href="https://www.mm-vision.dk/amd-ryzen-7-9700x-processor"><img src="https://img.mm-vision.dk/images/v1/mmv/amd-9000-series-ryzen-7-02.webp" alt="AMD Ryzen 7 9700X BOX" width="92"></a>|AMD Ryzen 7 9700X BOX|100-100001404WOF|¥45,000|¥47,800|販売可能掲載 ¥47,800（in_stock） / 売切れ0・在庫不明1・取寄せ/予約0・鮮度切れ0|verified_retailer_listing_reference|前倒し購入価格に未到達|verified: exact_identity_direct_price_and_pit_verified / stock=unknown; verified: exact_identity_direct_price_and_pit_verified / stock=in_stock|[価格比較ページ](https://shop.tsukumo.co.jp/goods/0730143315593/) / [100-100001404WOF 在庫不明 ¥53,110](https://www.yodobashi.com/product/100000001008661707/)|
|<a href="https://www.cclonline.com/90-mxbr7-a0uayz-asrock-b850m-pro-rs-wifi-matx-motherboard-for-amd-am5-cpus-476896/"><img src="https://www.cclonline.com/images/avante/B850M-Pro-RS-WiFi_box.jpg" alt="ASRock B850M Pro RS WiFi" width="92"></a>|ASRock B850M Pro RS WiFi|B850M Pro RS WiFi|¥20,000|未取得|販売可能な直接掲載価格なし / 売切れ1・在庫不明2・取寄せ/予約0・鮮度切れ0|missing|在庫未確認|verified: exact_identity_direct_price_and_pit_verified / stock=unknown; verified: exact_identity_direct_price_and_pit_verified / stock=out_of_stock; verified: exact_identity_direct_price_and_pit_verified / stock=unknown|[価格比較ページ](https://kakaku.com/item/K0001669878/) / [B850M Pro RS WiFi 在庫不明 ¥26,990](https://www.yodobashi.com/product/100000001008871801/) / [マザーボード(Socket AM5)   B850M Pro RS W 在庫不明 ¥32,080](https://www.sofmap.com/product_detail.aspx?sku=101393495) / [B850M Pro RS WiFi 売切れ ¥32,090](https://www.pc4u.co.jp/view/item/000000092844)|
|<a href="https://banin123.base.shop/items/131528972"><img src="https://baseec-img-mng.akamaized.net/images/item/origin/fe2f683b0a8212c0166b85f0c7969499.jpg?imformat=generic" alt="Corsair RM850e 2025 850W ATX 3.1 Gold" width="92"></a>|Corsair RM850e 2025 850W ATX 3.1 Gold|CP-9020296-JP|¥14,000|¥14,980|販売可能掲載 ¥14,980（in_stock）|verified_retailer_listing_reference|前倒し購入価格に未到達|verified: exact_identity_direct_price_and_pit_verified / stock=in_stock; unverified: direct_price_missing_or_not_integer / stock=unknown|[価格比較ページ](https://www.dospara.co.jp/SBR83/IC519918.html)|
|<a href="https://www.dateks.lv/en/cenas/korpusi/863822-fractaldesign-pop-air-black-tg-clear-tint"><img src="https://www.dateks.lv/images/pic/2400/2400/518/1239.jpg" alt="Fractal Design Pop Air TG" width="92"></a>|Fractal Design Pop Air TG|FD-C-POA1A-02|¥12,000|¥13,180|販売可能掲載 ¥13,180（in_stock） / 売切れ0・在庫不明0・取寄せ/予約1・鮮度切れ0|verified_retailer_listing_reference|前倒し購入価格に未到達|verified: exact_identity_direct_price_and_pit_verified / stock=preorder_or_backorder; verified: exact_identity_direct_price_and_pit_verified / stock=in_stock|[価格比較ページ](https://www.dospara.co.jp/SBR1959/IC480986.html) / [FD-C-POA1A-02 取寄せ/予約 ¥14,510](https://www.yodobashi.com/product/100000001007195271/)|
|<a href="https://shop.tsukumo.co.jp/goods/4549576190358/"><img src="https://cdn.tsukumo.co.jp/image/item/4549576190358_1.jpg" alt="Microsoft Windows 11 Home 日本語版 パッケージ版" width="92"></a>|Microsoft Windows 11 Home 日本語版 パッケージ版|HAJ-00094|¥17,000|¥19,280|販売可能掲載 ¥19,280（in_stock）|verified_retailer_listing_reference|前倒し購入価格に未到達|verified: exact_identity_direct_price_and_pit_verified / stock=in_stock|[価格比較ページ](https://www.yodobashi.com/product/100000001006975270/)|
|<a href="https://www.pccomponentes.com/memoria-ram-team-group-t-create-expert-ddr5-6000mhz-32gb-2x16gb-cl30-dual-amd-expo-e-intel-xmp-blanca"><img src="https://img.pccomponentes.com/articles/1086/10864724/394-team-group-t-create-expert-ddr5-6000mhz-32gb-2x16gb-cl30-dual-amd-expo-e-intel-xmp-blanca.jpg" alt="TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)" width="92"></a>|TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)|CTCWD532G6000HC38ADC01|¥58,000|未取得|販売可能な直接掲載価格なし / 売切れ0・在庫不明1・取寄せ/予約0・鮮度切れ0|missing|在庫未確認|verified: exact_identity_direct_price_and_pit_verified / stock=unknown; unverified: direct_price_missing_or_not_integer / stock=unknown|[価格比較ページ](https://kakaku.com/item/K0001610896/) / [TEAMGROUP (旧称 Team) T-CREATE EXPERT 在庫不明 ¥113,938](https://ymall.jp/store/mlymall/b0chf9th1b-20260811/)|
|<a href="https://www.cfd.co.jp/biz/product/release/ct1000p3pssd8jp.html"><img src="https://www.cfd.co.jp/webpim/product/image/c/crucial-p3-plus-m2-series/ct1000p3pssd8jp/ct1000p3pssd8jp__0100.jpg" alt="Crucial P3 Plus CT1000P3PSSD8JP 1TB" width="92"></a>|Crucial P3 Plus CT1000P3PSSD8JP 1TB|CT1000P3PSSD8JP|¥24,000|¥35,500（検索スニペット参考のみ）|販売可能な直接掲載価格なし / 売切れ3・在庫不明0・取寄せ/予約0・鮮度切れ0|search_snippet_reference_only|在庫切れ|verified: exact_identity_direct_price_and_pit_verified / stock=out_of_stock; verified: exact_identity_direct_price_and_pit_verified / stock=out_of_stock; verified: exact_identity_direct_price_and_pit_verified / stock=out_of_stock|[価格比較ページ](https://kakaku.com/item/K0001466997/) / [Crucial  P3 Plus CT1000P3PSSD8JP (M 売切れ ¥9,300](https://www.dospara.co.jp/SBR1144/IC481159.html) / [P3 Plus CT1000P3PSSD8JP [M.2 NVMe 内 売切れ ¥10,450](https://shop.tsukumo.co.jp/goods/0649528918970/) / [https://kaago.com/excellar/crucial% 売切れ ¥32,769](https://kaago.com/excellar/crucial%E3%80%80%E5%86%85%E8%94%B5%E5%9E%8B-M.2-SSD%E3%80%80P3-Plus-CT1000P3PSSD8JP%E3%80%801TB/?itemcode=0001000033094) / [検索ページ参考元](https://search.kakaku.com/Crucial%20P3%20Plus%20CT1000P3PSSD8JP%201TB/)|
|<a href="https://www.thermalright.com/product/peerless-assassin-120-se-v3/"><img src="https://thermalright.com/wp-content/uploads/2024/12/8-3-1024x1024.jpg" alt="Thermalright Peerless Assassin 120 SE V3" width="92"></a>|Thermalright Peerless Assassin 120 SE V3|Peerless Assassin 120 SE V3|¥5,000|¥4,980（検索スニペット参考のみ）|販売可能な直接掲載価格なし / 売切れ1・在庫不明0・取寄せ/予約0・鮮度切れ0|search_snippet_reference_only|在庫切れ|verified: exact_identity_direct_price_and_pit_verified / stock=out_of_stock|[価格比較ページ](https://kakaku.com/item/K0001789043/) / [Thermalright  Peerless Assassin 120 売切れ ¥4,980](https://www.dospara.co.jp/SBR1968/IC645423.html) / [検索ページ参考元](https://search.kakaku.com/Thermalright%20Peerless%20Assassin%20120%20SE%20V3/)|
|<a href="https://teknoklik.com/pny-geforce-rtx-5070-oc-12gb-dual-fan-slim-gddr7-192bit-vcg507012dfsxpb1-o-2744"><img src="https://teknoklik.com/images/product/pny/2745/pny-geforce-rtx-5070-oc-12gb-dual-fan-slim-gddr7-192bit-vcg507012dfsxpb1-o_1000x1000_NNAECGHFET.jpg" alt="PNY GeForce RTX 5070 12GB OC SLIM" width="92"></a>|PNY GeForce RTX 5070 12GB OC SLIM|VCG507012DFSXPB1-O|¥138,000|未取得|販売可能な直接掲載価格なし / 売切れ1・在庫不明1・取寄せ/予約0・鮮度切れ0|missing|在庫未確認|unverified: fetch_error / stock=unknown / RuntimeError / curl_http_403; verified: exact_identity_direct_price_and_pit_verified / stock=out_of_stock; verified: exact_identity_direct_price_and_pit_verified / stock=unknown|[価格比較ページ](https://kakaku.com/item/K0001798041/) / [PNY GeForce RTX 5070 12GB OC SLIM　V 在庫不明 ¥190,800](https://shop.tsukumo.co.jp/goods/0751492812151/?cid=kakakukcom) / [PNY GeForce RTX 5070 12GB OC SLIM   売切れ ¥190,800](https://www.sofmap.com/product_detail.aspx?eVar4=WBPT&sku=102194845)|

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
- **PASS**: os_license — Windows 11 Home license budgeted unless an existing transferable license is confirmed

### 自作VRAM案：Ryzen 7 9700X + RTX 5060 Ti 16GB

- BF目標総額（計画値）: ¥364,000。値下がり予測・実売の確定額ではない。
- 現時点の販売可能掲載: 5/9部品 / 部分合計 ¥225,040（掲載額だけ。完成価格・注文カート合計ではない）。
- 採用GPU SKU: PNY GeForce RTX 5060 Ti 16GB OC（keep_primary_exact_sku_if_fresh_in_stock）
- 採用RAM: TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)（primary_memory_fallback_no_verified_in_stock_alternative）
- 採用SSD: Crucial P3 Plus CT1000P3PSSD8JP 1TB（primary_fallback_no_verified_in_stock_alternative）
- 採用CPUクーラー: Thermalright Peerless Assassin 120 SE V3（primary_fallback_no_verified_in_stock_alternative）
- 現在の比較参考合計: 未算出。価格・型番・在庫条件を満たさない部品を0円補完しない
- 互換性: REVIEW / 判定: WAIT_FOR_COMPATIBILITY_REVIEW

|画像|部品|型番|BF目標|検証済み/表示専用参考値|直接掲載価格（在庫条件未達・推定不採用）|確認状態|前倒し購入シグナル|直接取得診断|リンク|
|---|---|---|---:|---:|---|---|---|---|---|---|
|<a href="https://www.mm-vision.dk/amd-ryzen-7-9700x-processor"><img src="https://img.mm-vision.dk/images/v1/mmv/amd-9000-series-ryzen-7-02.webp" alt="AMD Ryzen 7 9700X BOX" width="92"></a>|AMD Ryzen 7 9700X BOX|100-100001404WOF|¥45,000|¥47,800|販売可能掲載 ¥47,800（in_stock） / 売切れ0・在庫不明1・取寄せ/予約0・鮮度切れ0|verified_retailer_listing_reference|前倒し購入価格に未到達|verified: exact_identity_direct_price_and_pit_verified / stock=unknown; verified: exact_identity_direct_price_and_pit_verified / stock=in_stock|[価格比較ページ](https://shop.tsukumo.co.jp/goods/0730143315593/) / [100-100001404WOF 在庫不明 ¥53,110](https://www.yodobashi.com/product/100000001008661707/)|
|<a href="https://www.cclonline.com/90-mxbr7-a0uayz-asrock-b850m-pro-rs-wifi-matx-motherboard-for-amd-am5-cpus-476896/"><img src="https://www.cclonline.com/images/avante/B850M-Pro-RS-WiFi_box.jpg" alt="ASRock B850M Pro RS WiFi" width="92"></a>|ASRock B850M Pro RS WiFi|B850M Pro RS WiFi|¥20,000|未取得|販売可能な直接掲載価格なし / 売切れ1・在庫不明2・取寄せ/予約0・鮮度切れ0|missing|在庫未確認|verified: exact_identity_direct_price_and_pit_verified / stock=unknown; verified: exact_identity_direct_price_and_pit_verified / stock=out_of_stock; verified: exact_identity_direct_price_and_pit_verified / stock=unknown|[価格比較ページ](https://kakaku.com/item/K0001669878/) / [B850M Pro RS WiFi 在庫不明 ¥26,990](https://www.yodobashi.com/product/100000001008871801/) / [マザーボード(Socket AM5)   B850M Pro RS W 在庫不明 ¥32,080](https://www.sofmap.com/product_detail.aspx?sku=101393495) / [B850M Pro RS WiFi 売切れ ¥32,090](https://www.pc4u.co.jp/view/item/000000092844)|
|<a href="https://banin123.base.shop/items/131528972"><img src="https://baseec-img-mng.akamaized.net/images/item/origin/fe2f683b0a8212c0166b85f0c7969499.jpg?imformat=generic" alt="Corsair RM850e 2025 850W ATX 3.1 Gold" width="92"></a>|Corsair RM850e 2025 850W ATX 3.1 Gold|CP-9020296-JP|¥14,000|¥14,980|販売可能掲載 ¥14,980（in_stock）|verified_retailer_listing_reference|前倒し購入価格に未到達|verified: exact_identity_direct_price_and_pit_verified / stock=in_stock; unverified: direct_price_missing_or_not_integer / stock=unknown|[価格比較ページ](https://www.dospara.co.jp/SBR83/IC519918.html)|
|<a href="https://www.dateks.lv/en/cenas/korpusi/863822-fractaldesign-pop-air-black-tg-clear-tint"><img src="https://www.dateks.lv/images/pic/2400/2400/518/1239.jpg" alt="Fractal Design Pop Air TG" width="92"></a>|Fractal Design Pop Air TG|FD-C-POA1A-02|¥12,000|¥13,180|販売可能掲載 ¥13,180（in_stock） / 売切れ0・在庫不明0・取寄せ/予約1・鮮度切れ0|verified_retailer_listing_reference|前倒し購入価格に未到達|verified: exact_identity_direct_price_and_pit_verified / stock=preorder_or_backorder; verified: exact_identity_direct_price_and_pit_verified / stock=in_stock|[価格比較ページ](https://www.dospara.co.jp/SBR1959/IC480986.html) / [FD-C-POA1A-02 取寄せ/予約 ¥14,510](https://www.yodobashi.com/product/100000001007195271/)|
|<a href="https://shop.tsukumo.co.jp/goods/4549576190358/"><img src="https://cdn.tsukumo.co.jp/image/item/4549576190358_1.jpg" alt="Microsoft Windows 11 Home 日本語版 パッケージ版" width="92"></a>|Microsoft Windows 11 Home 日本語版 パッケージ版|HAJ-00094|¥17,000|¥19,280|販売可能掲載 ¥19,280（in_stock）|verified_retailer_listing_reference|前倒し購入価格に未到達|verified: exact_identity_direct_price_and_pit_verified / stock=in_stock|[価格比較ページ](https://www.yodobashi.com/product/100000001006975270/)|
|<a href="https://www.pccomponentes.com/memoria-ram-team-group-t-create-expert-ddr5-6000mhz-32gb-2x16gb-cl30-dual-amd-expo-e-intel-xmp-blanca"><img src="https://img.pccomponentes.com/articles/1086/10864724/394-team-group-t-create-expert-ddr5-6000mhz-32gb-2x16gb-cl30-dual-amd-expo-e-intel-xmp-blanca.jpg" alt="TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)" width="92"></a>|TeamGroup T-CREATE EXPERT White DDR5-6000 32GB (16GBx2)|CTCWD532G6000HC38ADC01|¥58,000|未取得|販売可能な直接掲載価格なし / 売切れ0・在庫不明1・取寄せ/予約0・鮮度切れ0|missing|在庫未確認|verified: exact_identity_direct_price_and_pit_verified / stock=unknown; unverified: direct_price_missing_or_not_integer / stock=unknown|[価格比較ページ](https://kakaku.com/item/K0001610896/) / [TEAMGROUP (旧称 Team) T-CREATE EXPERT 在庫不明 ¥113,938](https://ymall.jp/store/mlymall/b0chf9th1b-20260811/)|
|<a href="https://www.cfd.co.jp/biz/product/release/ct1000p3pssd8jp.html"><img src="https://www.cfd.co.jp/webpim/product/image/c/crucial-p3-plus-m2-series/ct1000p3pssd8jp/ct1000p3pssd8jp__0100.jpg" alt="Crucial P3 Plus CT1000P3PSSD8JP 1TB" width="92"></a>|Crucial P3 Plus CT1000P3PSSD8JP 1TB|CT1000P3PSSD8JP|¥24,000|¥35,500（検索スニペット参考のみ）|販売可能な直接掲載価格なし / 売切れ3・在庫不明0・取寄せ/予約0・鮮度切れ0|search_snippet_reference_only|在庫切れ|verified: exact_identity_direct_price_and_pit_verified / stock=out_of_stock; verified: exact_identity_direct_price_and_pit_verified / stock=out_of_stock; verified: exact_identity_direct_price_and_pit_verified / stock=out_of_stock|[価格比較ページ](https://kakaku.com/item/K0001466997/) / [Crucial  P3 Plus CT1000P3PSSD8JP (M 売切れ ¥9,300](https://www.dospara.co.jp/SBR1144/IC481159.html) / [P3 Plus CT1000P3PSSD8JP [M.2 NVMe 内 売切れ ¥10,450](https://shop.tsukumo.co.jp/goods/0649528918970/) / [https://kaago.com/excellar/crucial% 売切れ ¥32,769](https://kaago.com/excellar/crucial%E3%80%80%E5%86%85%E8%94%B5%E5%9E%8B-M.2-SSD%E3%80%80P3-Plus-CT1000P3PSSD8JP%E3%80%801TB/?itemcode=0001000033094) / [検索ページ参考元](https://search.kakaku.com/Crucial%20P3%20Plus%20CT1000P3PSSD8JP%201TB/)|
|<a href="https://www.thermalright.com/product/peerless-assassin-120-se-v3/"><img src="https://thermalright.com/wp-content/uploads/2024/12/8-3-1024x1024.jpg" alt="Thermalright Peerless Assassin 120 SE V3" width="92"></a>|Thermalright Peerless Assassin 120 SE V3|Peerless Assassin 120 SE V3|¥5,000|¥4,980（検索スニペット参考のみ）|販売可能な直接掲載価格なし / 売切れ1・在庫不明0・取寄せ/予約0・鮮度切れ0|search_snippet_reference_only|在庫切れ|verified: exact_identity_direct_price_and_pit_verified / stock=out_of_stock|[価格比較ページ](https://kakaku.com/item/K0001789043/) / [Thermalright  Peerless Assassin 120 売切れ ¥4,980](https://www.dospara.co.jp/SBR1968/IC645423.html) / [検索ページ参考元](https://search.kakaku.com/Thermalright%20Peerless%20Assassin%20120%20SE%20V3/)|
|<a href="https://www.idealo.es/precios/206267042/pny-geforce-rtx-5060-ti-dual-fan-oc-16gb.html"><img src="https://cdn.idealo.com/folder/Product/206267/0/206267042/s11_produktbild_max/pny-geforce-rtx-5060-ti-dual-fan-oc-16gb.jpg" alt="PNY GeForce RTX 5060 Ti 16GB OC" width="92"></a>|PNY GeForce RTX 5060 Ti 16GB OC|VCG5060T16DFXPB1-O|¥120,000|¥129,800|販売可能掲載 ¥129,800（in_stock）|verified_retailer_listing_reference|前倒し購入価格に未到達|verified: exact_identity_direct_price_and_pit_verified / stock=in_stock|[価格比較ページ](https://www.dospara.co.jp/SBR1892/IC625088.html)|

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
- **PASS**: os_license — Windows 11 Home license budgeted unless an existing transferable license is confirmed

## 注文直前の確認

- CPUソケット／BIOS／マザーボード対応、メモリ規格・QVL・EXPO安定性。
- GPUの正確な小売型番・カード寸法・厚さ・補助電源とケース干渉。
- 電源容量・規格・付属ケーブル、クーラー高とRAM干渉、ファン配置。
- 個別店の決済価格・送料・在庫・返品期限・保証・OSライセンス。
- 比較サイト参考価格は公式BF価格ではない。公式日程・店舗価格が確認できるまで買い時判定は保留。
