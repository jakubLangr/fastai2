from fastai2.basics import *
from fastai2.text.all import *
from fastai2.callback.all import *
from fastscript import *

path = untar_data(URLs.WIKITEXT_TINY)

def istitle(line):
    return len(re.findall(r'^ = [^=]* = $', line)) != 0

def read_file(filename):
    articles = L()
    with open(filename, encoding='utf8') as f:
        lines = f.readlines()
    current_article = ''
    for i,line in enumerate(lines):
        current_article += line
        if i < len(lines)-2 and lines[i+1] == ' \n' and istitle(lines[i+2]):
            articles.append(current_article.split(' '))
            current_article = ''
    articles.append(current_article.split(' '))
    return articles

def get_data(bs, sl):
    train = LM_Dataset(read_file(path/'train.txt'), bs=bs, seq_len=sl, shuffle=True)
    valid = LM_Dataset(read_file(path/'valid.txt'), bs=bs, seq_len=sl)
    count = Counter([p for t in train.ds for p in t])
    vocab = make_vocab(count)
    train_ds = TfmdLists(train, tfms=Numericalize(vocab), as_item=False, wrap_l=False)
    valid_ds = TfmdLists(valid, tfms=Numericalize(vocab), as_item=False, wrap_l=False)
    train_dl = TfmdDL(train_ds, bs=bs, sampler=LM_Sampler(train), num_workers=8)
    valid_dl = TfmdDL(valid_ds, bs=bs, sampler=LM_Sampler(valid), num_workers=8)
    return DataLoaders(train_dl, valid_dl),vocab

@call_parse
def main(gpu:Param("GPU to run on", int)=6,
         bs:Param("Batch size", int)=104,
         sl:Param("Sequence length", int)=72,
         qrnn:Param("Use QRNNs instead of LSTMs", bool)=False):
    dbch,vocab = get_data(bs, sl)
    config = awd_lstm_lm_config.copy()
    if qrnn: config.update({'input_p': 0.4, 'output_p': 0.4, 'weight_p': 0.1, 'embed_p': 0.1, 'hidden_p': 0.2})
    else:    config.update({'input_p': 0.6, 'output_p': 0.4, 'weight_p': 0.5, 'embed_p': 0.1, 'hidden_p': 0.2})
    model = get_language_model((AWD_QRNN if qrnn else AWD_LSTM), len(vocab), config=config) 
    opt_func = partial(Adam, wd=0.1, eps=1e-7)
    if qrnn: cb_funcs = [partial(MixedPrecision, clip=0.1), partial(RNNTrainer, alpha=2, beta=1)]
    else : cb_funcs = [partial(MixedPrecision, clip=0.1), partial(RNNTrainer, alpha=3, beta=2)]
    learn = Learner(model, dbch, loss_func=CrossEntropyLossFlat(), opt_func=opt_func, cb_funcs=cb_funcs, metrics=[accuracy, Perplexity()])
    learn.fit_one_cycle(90, 5e-3, moms=(0.8,0.7,0.8), div=10)

