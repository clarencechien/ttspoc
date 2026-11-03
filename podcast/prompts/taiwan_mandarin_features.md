# 台灣華語發音與用語特色（給 TTS 語氣指示與寫稿用）

2026-11-03 整理。只收主流、年輕台灣人普遍有的特色；刻板的「台灣國語」特徵（f 念成 h、「我們」念成「偶們」、ㄩ 念成 ㄧ）不放進指示，避免變成模仿。

## 發音
| 特色 | 例子 | 來源 |
|---|---|---|
| 捲舌弱化，ㄓㄔㄕ 接近 ㄗㄘㄙ | 「不是」接近「不四」、「只」接近「子」 | 維基百科〈臺灣國語〉；陽明交大與 PMC 的超音波研究 |
| 前後鼻音合併，ㄥ 和 ㄣ 不分 | 「模型」的型接近「信」、「應該」接近「因該」 | 維基百科；台灣華語語料研究 |
| 輕聲少 | 「東西」「消息」第二字保留原調 | 維基百科；台灣華語輕聲研究：普通話念輕聲的字，台灣約一半念輕聲 |
| 幾乎沒有兒化音 | 「一會」「小孩」 | 維基百科 |
| 連音、吞音 | 「這樣子」接近「醬子」、「不知道」接近「不照」 | 維基百科；台灣華語縮讀研究（縮讀程度與詞頻有關） |
| 咬字放鬆、嘴型小、調域較窄 | 語調起伏比普通話小 | 鏡週刊引述的聲學研究；使用者回饋 |
| 句尾語助詞帶尾音 | 喔、啦、嘛、齁 | 使用者回饋 |

## 用語
- 台灣說法：超、很扯、真的假的、欸你知道嗎、用猜的、更扯的是、找碴、醬（這樣）。
- 避免的大陸說法：更狠的是、盲猜、咱們、挺、這事兒、視頻、質量、信息、軟件、靠譜、立馬、整活、點贊。`script_lint.py` 會自動抓。

## 怎麼用在 TTS 上
- 語氣指示（`ep01.json` 的 `base_style_v4`）直接描述上面的發音特色，並要求素人感、不要播音腔。
- 稿子用台灣口語寫，連音可以直接寫成合音字（醬）。
- Gemini 評審分不出台灣腔與大陸腔，口音只能由台灣母語者判斷。

## 來源
- 臺灣國語，維基百科：https://zh.wikipedia.org/zh-tw/臺灣國語
- 你是台灣國語還是台灣狗蟻？一窺 11 種很「台」的發音，鏡週刊：https://www.mirrormedia.mg/story/20190425cul001
- Sibilant fricative merging in Taiwan Mandarin（ultrasound），PMC：https://pmc.ncbi.nlm.nih.gov/articles/PMC7891883/
- Unmerging the sibilant merger among speakers of Taiwan Mandarin，陽明交大：https://scholar.nycu.edu.tw/en/publications/unmerging-the-sibilant-merger-among-speakers-of-taiwan-mandarin/
- A study of neutral-tone syllables in Taiwan Mandarin：https://scholarspace.manoa.hawaii.edu/server/api/core/bitstreams/f3af0788-f9dd-45dd-9fd3-e05553d1becd/content
- Production and Perception of Taiwan Mandarin Syllable Contraction（Grace Kuo）：https://escholarship.org/content/qt6kj264nh/qt6kj264nh_noSplash_89141fb42d8051d8af0fb1e1539d1f44.pdf
- Lexical Effects in Phonemic Neutralization in Taiwan Mandarin：https://escholarship.org/content/qt8fq9s0hs/qt8fq9s0hs_noSplash_997efe2f0151d82f4eedcbbc77c17bb2.pdf
