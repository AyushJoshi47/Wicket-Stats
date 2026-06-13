import pandas as pd

df = pd.read_parquet('IPL.parquet')
a = df[['batter', 'bowler']].nunique()
print(a)