#!/usr/bin/python3
# coding: utf-8
"""
ピッチ曲線で音程を保持しつつ音符を結合するスクリプト
"""
import sys
from pprint import pprint

# import pysnooper

filepath = sys.argv[1]

TEST = False
original_tempo = 120.00
original_lengths = [480, 480, 480]
original_nns = [67, 64, 59]
original_pbss = [-25, -25, -25]
original_pbys = [[0.0], [0.0], [0.0]]
original_pbws = [[50.0], [50.0], [50.0]]
original_next_lyric = 'R'


def read_txt(path):
    """
    UTAUの一時データから必要な情報を読み取る。
    リストの要素を持つ辞書型を返す。
    """
    f = open(path, 'r+', encoding="utf-8_sig")
    line = f.readline()
    d = {'tempo': 60, 'length': [], 'lyric': [], 'notenum': [], 'pbw': [], 'pby': [], 'pbs': []}

    counter = 0
    while line:
        # print(line)
        line = f.readline().strip()
        # PREVを読まないようにする
        if counter < 3:
            if line.startswith('[#'):
                counter += 1
            # テンポを読み取る
            elif line.startswith('Tempo='):
                d['tempo'] = float(line[6:])

        # 選択範囲とNEXTのパラメータを読み取る
        else:
            if line.startswith('[#'):
                # 選択範囲の直後のノートの削除を回避
                if line == '[#NEXT]':
                    pass
                # 選択範囲のうち先頭のノートを認識
                elif counter == 3:
                    counter += 1
                # 選択範囲のうち先頭でないノートは削除
                else:
                    print('delete')
                    line = '[#DELETE]'

            # 長さを読み取る
            elif line.startswith('Length='):
                d['length'].append(int(line[7:]))
            # 歌詞を読み取る
            elif line.startswith('Lyric='):
                d['lyric'].append(line[6:])
            # 音階番号を読み取る
            elif line.startswith('NoteNum='):
                d['notenum'].append(int(line[8:]))
            # PBSを読み取ってリストで辞書に格納
            elif line.startswith('PBS='):
                d['pbs'].append(int(line.split(';')[0][4:]))
            # PBWを読み取ってリストで辞書に格納
            elif line.startswith('PBW='):
                d['pbw'].append(list(map(float, line[4:].split(','))))
            # PBYを読み取ってリストで辞書に格納
            elif line.startswith('PBY='):
                d['pby'].append(list(map(float, line[4:].split(','))))
            else:
                pass
    f.close()
    pprint(d)
    return d


def length_msec(tempo, length_ticks):
    """
    Tempo[beat/min] 480[Ticks/beat] を用いて、
    Length[Ticks] → Length[msec] の変換をする。
    """
    # sec_per_beat = 60 / tempo
    # ticks_per_beat = 480
    # sec_per_ticks = sec_per_beat / tick_per_beat
    # msec_per_ticks = sec_per_ticks * 1000
    # 以上をまとめると msec_per_ticks = int(1000 * 60 / 480 / tempo)
    # length_msec = length_ticks * msec_per_ticks
    # return int(length_msec)
    return int(125 * length_ticks // tempo)


def combine_length(lengths):
    """
    ノート長さを合算する。
    """
    combined_length = sum(lengths)
    print('Length結合完了 combined_length:', combined_length)
    return combined_length


def combine_pbw(tempo, lengths, pbss, pbws, next_lyric):
    """
    PBWを一つにまとめる。
    PBSに起因する点の位置に注意
    Length[Ticks] と PBW[msec] の単位変換が必要なことに注意
    終端のピッチ点のタイミングに注意
    """
    # まとめたPBW用リスト
    combined_pbw = []

    # ノート数
    num_note = len(lengths)

    for n in range(num_note):
        # 先頭ノートはとくに何もしない
        if n == 0:
            # まとめPBWに追記
            combined_pbw += pbws[n]

        # 先頭以外のノートはピッチ点位置（時刻）を計算してずらす
        # また、左側PBSの部分を組み込む必要がある
        elif n != num_note - 1:
            # 前のノートの音程維持用のピッチ点（ポルタメント開始位置に相当）を追加
            combined_pbw.append(
                length_msec(tempo, lengths[n - 1])
                - pbss[n - 1] - sum(pbws[n]) + pbss[n])
            # まとめPBWに追記
            combined_pbw += pbws[n]

        # 最終ノートは選択範囲外との接続のためのピッチ点の処理が必要
        elif n == num_note - 1:
            # 前のノートの音程維持用のピッチ点（ポルタメント開始位置に相当）を追加
            combined_pbw.append(
                length_msec(tempo, lengths[n - 1])
                - pbss[n - 1] - sum(pbws[n]) + pbss[n])

            # NEXTが休符Rの場合は最後までピッチを維持
            if next_lyric == 'R':
                pbws[n].append(length_msec(tempo, lengths[n]) - sum(pbws[n]) - pbss[n])
                pbws[n].append(0.0)
            # NEXTが休符Rでない場合は最終ノートとNEXTのPBSが同一と仮定してピッチ点を決定
            # 実際にNEXTのPBSを読んでもいいのですが、ピッチ順序が狂う可能性があるので未実装
            else:
                pbws[n].append(length_msec(tempo, lengths[n]) - pbws[n])
                pbws[n].append(0.0)

            # まとめPBWに追記
            combined_pbw += pbws[n]

    print('PBW結合完了    combined_pbw:', combined_pbw)
    return combined_pbw


def combine_pby(nns, pbys):
    """
    PBYを一つにまとめる。
    PBSに相当するピッチ点は前のノート音高依存なことに注意
    """
    # まとめたPBY用リスト
    combined_pby = []

    # ノート数
    num_note = len(nns)

    # 各ノートのPBYを調製して追加していく
    for n in range(num_note):
        # 先頭ノートはピッチシフトの必要がない
        if n == 0:
            if TEST:
                print('----- case1: 先頭ノート -----')
                print('nns[{0}]  : {1}'.format(n, nns[n]))
                print('pbys[{0}] : {1}'.format(n, pbys[n]))
            pbys[n].append(0.0)
            # まとめPBYに追記
            combined_pby += pbys[n]

        # それ以降は先頭ノートの音高に応じてピッチシフトが必要
        elif n != num_note - 1:
            if TEST:
                print('----- case2: 中間ノート -----')
                print('nns[{0}]  : {1}'.format(n, nns[n]))
                print('pbys[{0}] : {1}'.format(n, pbys[n]))
            height_distance = (nns[0] - nns[n]) * (-10.0)
            # 音程を維持するためのピッチ点を追加
            pbys[n].append(0.0)
            # 先頭ノート音高に合わせてピッチシフト
            pbys[n] = list(map(lambda x: x + height_distance, pbys[n]))
            # まとめPBYに追記
            combined_pby += pbys[n]

        # 末尾のノートだけ処理が増える
        elif n == num_note - 1:
            if TEST:
                print('----- case3: 末尾ノート -----')
                print('nns[{0}]  : {1}'.format(n, nns[n]))
                print('pbys[{0}] : {1}'.format(n, pbys[n]))
            height_distance = (nns[0] - nns[n]) * (-10.0)
            # 音程を維持するためのピッチ点を追加
            pbys[n].append(0.0)
            # 先頭ノート音高に合わせてピッチシフト
            pbys[n] = list(map(lambda x: x + height_distance, pbys[n]))
            # 選択範囲外のノートにつなげるためのピッチ点を追加
            pbys[n].append(0.0)
            # まとめPBYに追記
            combined_pby += pbys[n]

        # 念のため
        else:
            print('\n----- case4: ERROR -----------------orz--')
            print('PBYの処理に失敗してしまいました。')
            print('想定外の条件に分岐しました。')
            print('配布者に連絡してくださると嬉しいです。')
            input('---------------- Press enter to exit. --')
            sys.exit()

    print('PBY結合完了    combined_pby:', combined_pby)
    return combined_pby


def main():
    """
    全体の処理を実行する関数。
    """
    read_txt(filepath)
    combine_length(original_lengths)
    combine_pbw(original_tempo, original_lengths, original_pbss, original_pbws, original_next_lyric)
    combine_pby(original_nns, original_pbys)


if __name__ == '__main__':
    main()
