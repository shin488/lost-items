STORAGE_KEY = "lost_items_v4"
CATEGORIES_KEY = "lost_items_categories_v1"
FLOORPLAN_KEY = "lost_items_floorplan_v1"
MAX_GRID = 30
DEFAULT_CATEGORIES = ["財布", "鍵", "スマホ", "イヤホン", "傘", "本", "文房具", "衣類", "カバン", "その他"]
WEEKDAYS_JP = ["月曜", "火曜", "水曜", "木曜", "金曜", "土曜", "日曜"]

DEFAULT_TENDENCIES = {
    "財布": ["ズボンのポケット", "カバンの中", "机の上", "ベッドの上"],
    "鍵": ["玄関の鍵穴", "カバンの中", "机の上", "ポケット"],
    "スマホ": ["布団の隙間", "ソファの隙間", "机の上", "ベッドの上"],
    "イヤホン": ["ポケット", "カバンの中", "机の上", "ベッドの上"],
    "傘": ["玄関", "会社/学校", "電車の中", "駐輪場"],
    "本": ["机の上", "カバンの中", "ベッドの上", "リビング"],
    "文房具": ["机の上", "カバンの中", "引き出しの中"],
    "衣類": ["洗濯機", "クローゼット", "ハンガー"],
    "カバン": ["玄関", "机の上", "車の中", "会社/学校"],
    "その他": ["ポケット", "カバンの中", "机の上", "ソファの隙間"],
}

RWR_ALPHA = 0.3
RWR_ITERATIONS = 20
RWR_CONVERGENCE = 1e-8
LOC_SIM_THRESHOLD = 0.15
LOC_SIM_DECAY = 0.3
LOC_TEMPORAL_WEIGHT = 0.4
LOC_TEMPORAL_BASE = 0.6
RECENCY_HALFLIFE_DAYS = 30
DOW_WEIGHTS = {0: 1.0, 1: 0.5, 6: 0.5}
DOW_OTHER = 0.2
HOUR_SIGMA_SQ = 18
RELATED_SCORE_THRESHOLD = 0.01
