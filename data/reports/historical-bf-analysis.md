# 過去のブラックフライデー資料：値下げ幅と時期の参考

> 初期集計版。出典付きのキャンペーン20記録・商品価格27件（2023〜2025年）をまとめる。通常価格の裏付けが弱い例、構成が要件に足りない例、二次資料は注記し、2026年の値下げ確率や確定価格へ読み替えない。内容は `scripts/historical_bf_analysis.py` により監視サイクルで再集計する。

## まず分かること

- Amazonの本セールは2023〜2025年の公式記録で、いずれも11月末〜12月初めの8日間。先行セールは2023/2024年が2日、2025年が3日と違いがある。
- PC専門店のセールは、オンラインと店頭で日程がずれる場合がある。店頭の目玉商品は日替わり・数量限定の報道例もあり、来店時点の型番・在庫・値段確認が必要。
- 2025年のRTX 5070 BTOで、¥249,800の報道例はメモリ16GBで今回の32GB条件を満たさない。一方、TSUKUMOのRTX 5070・32GB/1TB BTOが¥267,800という二次報道もある。いずれもBTOの実例であって、自作パーツ価格の合計や2026年の価格予測ではない。
- 公表通常価格とセール価格が分かる個別例では、モニターやマウスに約11〜36%の差が見える。ただしモデルも販売チャネルも異なるため、この割合を今回狙う型番の値下げ確率・期待値として使わない。
- 2026年は、各店の「2026年と明記された公式期間」と、その期間に取れた同一SKUの実売価格が揃うまで、セール前参考価格を「BF実売」と扱わない。

## 開催期間の履歴

|販売元・チャネル|年|確認できた開催期間|根拠|注記|
|---|---:|---|---|---|
|Amazon オンライン本セール|2023|11/24〜12/1|[Amazon公式](https://www.aboutamazon.jp/news/guide/six-key-points-to-make-your-shopping-at-amazon-black-friday-more-affordable-and-convenient)|8日間|
|Amazon 先行セール|2023|11/22〜11/23|[Amazon公式](https://www.aboutamazon.jp/news/guide/six-key-points-to-make-your-shopping-at-amazon-black-friday-more-affordable-and-convenient)|日付単位で保存|
|Amazon オンライン本セール|2024|11/29〜12/6|[Amazon Japan発表](https://prtimes.jp/main/html/rd/p/000001943.000004612.html)|8日間|
|Amazon 先行セール|2024|11/27〜11/28|[Amazon Japan発表](https://prtimes.jp/main/html/rd/p/000001952.000004612.html)|商品によって露出時刻は異なる|
|Amazon オンライン本セール|2025|11/24〜12/1|[Amazon公式](https://www.aboutamazon.jp/news/retail/amazon-black-friday-2025)|8日間|
|Amazon 先行セール|2025|11/21〜11/23|[Amazon公式](https://www.aboutamazon.jp/news/retail/amazon-black-friday-2025)|3日間|
|ドスパラ オンライン|2023|11/17 11:00〜12/1 10:59|[ドスパラ公式](https://www.dospara.co.jp/event/black-friday-2023-entry.html)|ポイント抽選キャンペーンを含む|
|ドスパラ 店舗|2023|11/17開店〜11/30閉店|[ドスパラ公式](https://www.dospara.co.jp/event/black-friday-2023-entry.html)|通販と別期間|
|ドスパラ オンライン/店舗|2024|11/22〜12/2（通販）／11/22〜12/1（店頭）|[GameWith（二次資料）](https://gamewith.jp/gaming-pc/531110)|公式日付の二次資料|
|パソコン工房 オンライン|2023|11/21〜12/4 10:59|[パソコン工房公式](https://www.iiyama-pc.jp/info/2023112101.php)|公式リリースで実施期間を確認|
|パソコン工房 オンライン|2024|11/19〜12/2 16:59|[パソコン工房公式](https://www.iiyama-pc.jp/info/20241119.php)|対象BTO最大5万円引き。最大額は平均ではない|
|パソコン工房 店舗|2024|11/22〜11/29|[パソコン工房公式](https://www.iiyama-pc.jp/info/2024112102.php)|店頭キャンペーン|
|パソコン工房 オンライン|2025|開始日は未確定、12/2 17:00終了と報道|[PC Watch](https://pc.watch.impress.co.jp/docs/news/2065065.html)|記事が掲載された日を開始日と断定しない|
|パソコン工房 店舗|2025|11/22〜11/28|[PC Watch](https://pc.watch.impress.co.jp/docs/news/2065588.html)|日替わり特価の報道|
|マウスコンピューター オンライン|2024|11/13〜12/4 10:59|[ITmedia PC USER](https://www.itmedia.co.jp/pcuser/spv/2411/13/news158.html)|モデルごとに値引き幅が異なる|
|Lenovo オンライン|2024|11/15〜11/28|[Lenovoのキャンペーンページ](https://www.lenovo.com/jp/ja/blackfriday/)|過去ページの掲載期間|
|Lenovo オンライン|2025|11/14〜12/4|[Lenovo公式](https://www.lenovo.com/jp/ja/campaigns/black-friday/)|期間は年度によって変わる|
|TSUKUMO BTO|2025|11/21 10:00〜12/2 10:00|[PC-Para（二次資料）](https://pc-para.jp/tsukumo/tsukumo-black-friday/)|公式の個別掲載を優先して再確認|
|TSUKUMO 店舗|2025|11/22〜11/28|[PC-Para（二次資料）](https://pc-para.jp/tsukumo/tsukumo-black-friday/)|店頭・BTOで期間が違う|

## 具体的な価格履歴の例

|年|販売チャネル|商品・構成|確認価格|比較参考価格|算術上の差|判断上の注意|
|---:|---|---|---:|---:|---:|---|
|2025|PC工房・オンラインBTO|Ryzen 7 9700X / RTX 5070 / 16GB / 1TB|¥249,800|¥299,800（¥50,000オフの逆算）|約16.7%|[PC Watch](https://pc.watch.impress.co.jp/docs/news/2065065.html)。参考価格は逆算値で、独立確認した通常価格ではない。RAM16GBのため今回の条件不適合。|
|2025|TSUKUMO・オンラインBTO|Core Ultra 7 265KF / RTX 5070 / 32GB / 1TB|¥267,800|未確認|—|[Gamepedia](https://premium.gamepedia.jp/shopping/archives/54417)などの二次報道。BTO価格であり自作価格ではない。|
|2025|TSUKUMO・オンラインBTO|Ryzen 7 7800X3D / RTX 5080 / 32GB / 1TB|¥349,800|未確認|—|[PC-Para](https://pc-para.jp/tsukumo/tsukumo-black-friday/)。GPU/CPUが異なり直接比較不可。|
|2025|TSUKUMO・オンラインBTO|Ryzen 9 9900X3D / RTX 5070 Ti / 64GB / 2TB|¥379,800|未確認|—|[PC-Para](https://pc-para.jp/tsukumo/tsukumo-black-friday/)。大穴の参考で、今回のDIY同等構成価格ではない。|
|2024|PC工房・オンラインBTO|Core i7-14700KF / RTX 4070 Ti SUPER / 16GB / 1TB|¥337,800|¥387,800|約12.9%|[PC工房公式](https://www.iiyama-pc.jp/info/20241119.php)。RAM16GBのため今回の条件不適合。|
|2024|Amazon・モニター|MSI PRO MP2412 / 23.8型 FHD 100Hz|¥9,980|¥14,800（メーカーの発売時価格目安）|約32.6%|[Game Watch](https://game.watch.impress.co.jp/docs/news/1642353.html)。今回の27型WQHDゲーミングモニターとは別クラス。|
|2024|Lenovo・モニター|D24-40 / 23.8型 FHD|¥13,200|¥19,800|約33.3%|[Lenovoキャンペーン](https://www.lenovo.com/jp/ja/blackfriday/)。個別製品の公式セール表記。|
|2024|Lenovo・モニター|L27i-4A / 27型 FHD 100Hz|¥15,800|¥17,820|約11.3%|[Lenovoキャンペーン](https://www.lenovo.com/jp/ja/blackfriday/)。WQHDではない。|
|2024|Lenovo・マウス|Yoga Pro Mouse|¥3,999|¥5,500|約27.3%|[Lenovoキャンペーン](https://www.lenovo.com/jp/ja/blackfriday/)。オフィス用途の製品でG304とは別モデル。|
|2024|Lenovo・キーボード|Lenovo keyboard (model not recorded)|¥10,890|¥15,950|約31.7%|[Lenovoキャンペーン](https://www.lenovo.com/jp/ja/blackfriday/)。ポイント付与は現金値引きに算入しない。|
|2025|GRAPHT・オンライン/店頭|GR2724ML-BK ゲーミングモニター|¥34,980|¥54,980|約36.4%|[メーカー告知](https://grapht.tokyo/news/grapht_blackfriday_2025)。販路別の取扱いに差がある。|
|2025|GRAPHT・オンライン/店頭|GRAPHT Omni マウスパッド|¥2,970|¥3,960|25.0%|[メーカー告知](https://grapht.tokyo/news/grapht_blackfriday_2025)。現行候補のマウスパッドとは別商品。|

さらに価格記録には、2024年AmazonのI-O Data FHD/WQHDモニター、2025年AmazonのBenQ MOBIUZとI-O Dataモニター、2025年PC工房店頭の型番未特定キーボード/マウス/電源/Radeon GPUを収録している。型番不明の店頭品は、今回買うG213r/G304/AOCなどの同一製品実績とは見なさない。

## どのように2026年の判断に使うか

1. **時期の判断**：過去のキャンペーン期間は監視窓を組む参考にするだけ。2026年の開始日/終了日は各社の公式発表で確認する。
2. **価格の判断**：同一SKUのBF前直接価格、BF期間中に確認した価格、セール後価格を別々に記録する。検索スニペットや違う構成の値段を現在価格やBF実売として扱わない。
3. **目標値の判断**：過去の類似クラスは目安にするが、構成・世代・RAM/SSD・販売方式が揃わない値段から「今年は何%下がる」とは断定しない。
4. **買い時の判断**：Web購入のPCパーツは最終カート価格・送料・在庫・互換性で判定。店頭購入のメインモニター、マウス、キーボード、スピーカーは、福岡の支店在庫・店頭レジ価格を確認するまで「店頭購入可能」と判定しない。
5. **値下がり率・確率**：比較可能な同一製品/同等構成の観測が少ないため、現時点で統計的な「値下げ確率」や典型割引率は出さない。収録点数だけ増やすのではなく、出典・型番・メモリ/SSD・販売チャネルの完全性を重視する。
