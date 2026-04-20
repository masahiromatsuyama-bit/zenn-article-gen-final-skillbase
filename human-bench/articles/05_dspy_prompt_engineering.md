# プロンプトエンジニアリングを終わらせるDSPy

**著者:** HELLO_CYBERNETICS
**出典:** https://zenn.dev/cybernetics/articles/39fb763aca746c
**公開日:** 2025/10/09

---

## はじめに

DSPyは手動のプロンプトエンジニアリングを排除する可能性を秘めています。この技術はディープラーニングのフレームワークと同じような考え方に基づいており、"これまで人手で頑張ってきたことを、パラメータに置き換えて、教師データで訓練してしまおう"という方針を実現しています。

## DSPyの基本概念

DSPyでは、プロンプトを明示的に書かず、入出力のシグネチャとやってほしい処理を与えるだけで出力を得られます。内部的には、"入出力を結びつけるような上手なプロンプト（あるいはその埋め込み表現）"が訓練されます。

## 実装例：ナルト口調変換

### モデルの作成

シグネチャで入出力を定義し、Moduleクラスで処理を実装します：

```python
class NarutoSignature(dspy.Signature):
    polite_sentence = dspy.InputField(desc="です・ます調の落ち着いた一文")
    rationale = dspy.OutputField(desc="変換時の推論過程")
    transformed = dspy.OutputField(desc="ナルト口調に変換した文")

class NarutoStyleChain(dspy.Module):
    def __init__(self):
        super().__init__()
        self.generator = dspy.ChainOfThought(NarutoSignature)
```

### 教師データの作成

```python
easy_example = dspy.Example(
    polite_sentence="今日の会議では議論を丁寧にまとめます。",
    transformed="オレが今日の会議をビシッとまとめてやるってばよ！",
    rationale="敬体をくだけた表現に置き換え"
).with_inputs("polite_sentence")
```

### 最適化アルゴリズム

**COPRO** または **GEPA** を使用してプロンプトを自動最適化します。GEPAでは反省用LLMがフィードバックから改善案を提案し、プロンプトを段階的に改善します。

## 訓練結果

最適化前："今日の会議では議論を丁寧にまとめるよ。でもさ、みんなの意見もちゃんと聞かないとね！"

最適化後："今日の会議では議論を丁寧にまとめるってばよ！でもさ、みんなの意見も大事だから、しっかり聞くぜ！"

最適化後は、よりナルトのキャラクター特性が反映された出力が得られました。

## 結論

DSPyを用いることで、PyTorchのような直感的なコードでプロンプト最適化を実装できます。GEPAアルゴリズムによる自動最適化により、手動でプロンプトをチューニングする手間が大幅に削減されます。
