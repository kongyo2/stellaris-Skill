---
name: stellaris-modding
description: Use when creating, editing, or reviewing Stellaris mods and you need self-contained guidance on Clausewitz/PDX script structure, file placement, scopes, triggers, effects, on_actions, events, technologies, buildings, districts, POP/jobs, traits, governments, relics, archaeology, decisions, special projects, situations, megastructures, components, zones, or vanilla-aligned conventions informed by CWTools and vanilla Stellaris.
---

# Stellaris Modding

Stellaris mod 制作のための documents-only な self-contained reference skill。
bundled `references/` だけで判断できるように構成している。ローカル環境の追加資料、補助ツール、外部サイトの存在は前提にしない。ユーザーが別途ファイルを与えた場合だけ、それを追加の一次資料として扱う。

## 基本方針

1. まず対象ドメインを決める。
2. そのドメインに最も近い reference を先に読む。
3. スコープや論理条件が怪しいときは、必ず基礎 reference に戻る。
4. 構文上は書けそうでも、実運用はバニラ慣習に従う。

## 読み始め

### 基礎

| トピック | リファレンス | 用途 |
|---|---|---|
| PDXスクリプト基礎 | [1.基礎概念](references/1.基礎概念.md) | 構文、エンコーディング、コメント、変数 |
| 条件式と論理演算 | [2.条件式と論理演算](references/2.条件式と論理演算.md) | AND/OR/NOT/NOR/NAND、`calc_true_if` |
| スコープ | [3.スコープ](references/3.スコープ.md) | `root`、`from`、`prev`、主要スコープ遷移 |

### 主要コンテンツ

| トピック | リファレンス | 用途 |
|---|---|---|
| アノマリー | [4.アノマリー](references/4.アノマリー.md) | anomaly category、`on_success`、anomaly event |
| イベント | [5.イベント](references/5.イベント.md) | event type、`option`、`after`、継承 |
| テクノロジー | [6.テクノロジー](references/6.テクノロジー.md) | `potential`、`weight_modifier`、`technology_swap` |
| オンアクション | [7.オンアクション](references/7.オンアクション.md) | `events`、`random_events`、スコープ一覧 |
| エフェクト | [8.エフェクト](references/8.エフェクト.md) | 制御構文、生成、変数、反復、scripted effect |
| 政府 | [9.政府](references/9.政府.md) | authority、civic、origin、government |
| 遺物・考古学 | [10.遺物・考古学サイト](references/10.遺物・考古学サイト.md) | relic、artifact action、archaeological site |
| POPと職業 | [11.POPと職業](references/11.POPと職業.md) | pop category、job、`swappable_data`、経済カテゴリ連携 |
| 特性 | [12.特性](references/12.特性.md) | species trait、leader trait、`replace_traits` |
| 惑星地形と惑星補正 | [13.惑星地形と惑星補正](references/13.惑星地形と惑星補正.md) | deposit、blocker、planet modifier |
| 建造物とディストリクト | [14.建造物とディストリクト](references/14.建造物とディストリクト.md) | building、district、`building_sets`、`convert_to` |
| 惑星ディシジョン | [15.惑星ディシジョン](references/15.惑星ディシジョン.md) | `potential`、`allow`、`effect`、`resources` |
| スペシャルプロジェクト | [16.スペシャルプロジェクト](references/16.スペシャルプロジェクト.md) | `requirements`、`on_success`、`abort_trigger` |

### 追加で読むべき reference

| トピック | リファレンス | 読むタイミング |
|---|---|---|
| 実装規約と上書き原則 | [17.実装規約と上書き原則](references/17.実装規約と上書き原則.md) | どのファイルに置くか、どこまで上書きするか迷うとき |
| shared logic の設計 | [18.scripted_effects・scripted_triggers・inline_scripts](references/18.scripted_effects・scripted_triggers・inline_scripts.md) | 共通化、再利用、パラメータ化を考えるとき |
| 経済カテゴリと zones | [19.経済カテゴリ・triggered_modifier・zones](references/19.経済カテゴリ・triggered_modifier・zones.md) | jobs/buildings/districts の出力や 4.0 zone 設計を触るとき |
| 高位システムの入口 | [20.高度システム索引](references/20.高度システム索引.md) | situation、megastructure、component、system initializer を触るとき |

## 実務ルール

- `scope`、`trigger`、`effect` が曖昧なら、先に基礎 reference を読む。
- 頻繁に発火するイベントは `is_triggered_only = yes` と `pre_triggers` を優先する。
- `MTTH` や重いポーリングより、`on_action`、遅延イベント、shared logic を優先する。
- 似た定義を複製する前に、`convert_to`、`technology_swap`、`swappable_data`、`scripted_effects`、`scripted_triggers`、`inline_script` で吸収できないか考える。
- jobs/buildings/districts の出力変更は、個別定義だけでなく経済カテゴリの継承も確認する。
- `triggered_*_modifier` はツールチップ表示と実適用がズレやすいので、必要なら `custom_tooltip` で補足する。
- 外部資料がない限り、この skill では「bundled references に書いてあること」だけを根拠に結論を組み立てる。
