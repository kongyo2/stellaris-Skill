---
name: stellaris-modding
description: |
  Stellaris mod開発支援スキル。CWToolsバリデーションルール、ゲームバージョン情報、PDXスクリプト構文リファレンスを提供。

  Use when:
  - Creating or editing Stellaris mods (イベント、テクノロジー、建造物、特性など)
  - Writing PDX script code (triggers, effects, scopes, modifiers)
  - Checking if a trigger/effect/scope exists and how to use it
  - Looking up correct syntax for Stellaris scripting
  - Validating mod elements against CWTools rules
  - Getting current Stellaris game version info
  - Understanding Stellaris modding concepts (スコープ、条件式、on_action等)
---

# Stellaris Modding

Stellaris mod開発を支援。CWToolsバリデーションルールへの動的アクセスとPDXスクリプトリファレンスを提供。

## クイックリファレンス

### Mod作成のための基礎知識

| トピック | リファレンス | 内容 |
|---------|-------------|------|
| PDXスクリプト基礎 | [1.基礎概念.md](references/1.基礎概念.md) | Clausewitz構文、データ型、エンコーディング |
| 条件判定 | [2.条件式と論理演算.md](references/2.条件式と論理演算.md) | AND/OR/NOT、複合条件 |
| コンテキスト切替 | [3.スコープ.md](references/3.スコープ.md) | root/from/prev、スコープチェーン |

### ゲームコンテンツ作成

| トピック | リファレンス | 内容 |
|---------|-------------|------|
| イベント | [5.イベント.md](references/5.イベント.md) | country_event、選択肢、チェーン |
| アノマリー | [4.アノマリー.md](references/4.アノマリー.md) | 調査イベント、発見システム |
| テクノロジー | [6.テクノロジー.md](references/6.テクノロジー.md) | 研究ツリー、解除条件 |
| オンアクション | [7.オンアクション.md](references/7.オンアクション.md) | ゲームイベントフック |
| エフェクト | [8.エフェクト.md](references/8.エフェクト.md) | ゲーム状態変更コマンド |

### 帝国・惑星システム

| トピック | リファレンス | 内容 |
|---------|-------------|------|
| 政府 | [9.政府.md](references/9.政府.md) | 政体、国是、権威 |
| 遺物・考古学 | [10.遺物・考古学サイト.md](references/10.遺物・考古学サイト.md) | 発掘、アーティファクト |
| POP・職業 | [11.POPと職業.md](references/11.POPと職業.md) | 人口、雇用、階層 |
| 特性 | [12.特性.md](references/12.特性.md) | 種族特性、リーダー特性 |
| 惑星地形 | [13.惑星地形と惑星補正.md](references/13.惑星地形と惑星補正.md) | 地形タイプ、惑星補正 |
| 建造物 | [14.建造物とディストリクト.md](references/14.建造物とディストリクト.md) | 惑星建造物、区域 |
| 惑星決定 | [15.惑星ディシジョン.md](references/15.惑星ディシジョン.md) | プレイヤー決定アクション |
| 特別計画 | [16.スペシャルプロジェクト.md](references/16.スペシャルプロジェクト.md) | 研究プロジェクト |

---

## ツール (scripts/)

Python 3.10+、外部依存なし。トリガー/エフェクト/スコープ/列挙型の検証に使用。

### 1. バージョン情報

```bash
python scripts/get_stellaris_version.py --minimal
# → Stellaris 4.2.3 (Build 21132326)
```

### 2. 要素の存在確認 (Level 1 - 軽量)

```bash
# 要素の存在チェック（最も軽量）
python scripts/fetch_cwtools_index.py --check has_technology
# → {"exists": true, "categories": ["trigger"]}

# パターンでフィルタ
python scripts/fetch_cwtools_index.py --category effect --filter "create_*"

# カテゴリ概要
python scripts/fetch_cwtools_index.py --summary
```

### 3. 要素の詳細取得 (Level 2/3)

```bash
# シグネチャ（Level 2）
python scripts/fetch_cwtools_element.py effect create_fleet

# フル定義（Level 3）
python scripts/fetch_cwtools_element.py effect create_fleet --full

# スコープ情報
python scripts/fetch_cwtools_element.py scope Country

# 列挙型の値
python scripts/fetch_cwtools_element.py enum leader_classes
```

### 4. 横断検索

```bash
# キーワード検索（全カテゴリ）
python scripts/search_cwtools.py fleet --limit 10

# 関連要素検索
python scripts/search_cwtools.py create_fleet --category effect --related
```

---

## 使用パターン

### Mod要素を書く前に確認

```bash
# 1. 存在確認（軽量）
python scripts/fetch_cwtools_index.py --check has_technology

# 2. 構文確認（必要時のみ）
python scripts/fetch_cwtools_element.py trigger has_technology
```

### 正確なパラメータを知りたい

```bash
# シグネチャで概要を見て
python scripts/fetch_cwtools_element.py effect add_modifier

# 複雑なら完全定義
python scripts/fetch_cwtools_element.py effect add_modifier --full
```

### 名前がわからない

```bash
# キーワードで検索
python scripts/search_cwtools.py population --limit 10

# 類似要素を探す
python scripts/search_cwtools.py create_army --category effect --related
```

---

## Progressive Disclosure

| 情報量 | コマンド | トークン目安 |
|--------|---------|-------------|
| 最小 | `--check NAME` | ~50 |
| 一覧 | `--filter "pattern*"` | ~100-500 |
| 概要 | `element.py cat NAME` | ~200 |
| 完全 | `element.py cat NAME --full` | ~500+ |

---

## キャッシュ

データは `~/.cache/stellaris-modding-skill/` に24時間キャッシュ。

```bash
python scripts/github_fetcher.py cache-info   # 状態確認
python scripts/github_fetcher.py clear-cache  # クリア
```
