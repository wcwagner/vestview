import requests
import datetime
from datetime import timedelta
from mwviews.api import PageviewsClient

def parse_date_str(date_str):
    """
    Converts date strs to form YYYYMMDD
    """
    date_formats = ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d",
                    "%m-%d-%Y", "%m/%d/%Y", "%m.%d.%Y", "%m%d%Y",
                    "%d-%m-%y", "%d/%m/%y", "%d.%m.%y", "%d%m%Y"]
    for fmt in date_formats:
        try:
            dt = datetime.datetime.strptime(date_str, fmt)
            return datetime.datetime.strftime(dt, '%Y%m%d')
        except ValueError:
            pass
    raise ValueError("couldn't parse dates, please use -h for accepted formats")

def _get_symbol_ids_and_wiki_titles(conn):
    """
    Retrieves list for all symbol ids and their respective wikipedia page title
    for every symbol in the symbol table.

    Returns:
        list: [(id, wiki_title) for every ticker found in the database]
    """
    cur = conn.cursor()
    cur.execute('SELECT id, wiki_title FROM symbol')
    rows = cur.fetchall()
    cur.close()
    return [(row[0], row[1]) for row in rows]

def _get_snp500_wiki_views(conn, start, end):
    """
    Inserts wiki page views into the daily_views table

    Parameters:
        start (str) : YYYYMMDD
        end   (str) : YYYYMMDD

    Returns:
        List[tuple] : (id, date, views, now, now)
    """
    pvc = PageviewsClient()
    symbol_ids_and_titles = _get_symbol_ids_and_wiki_titles(conn)
    title_to_id = { title:id for id, title in symbol_ids_and_titles }
    articles = [ title for _, title in symbol_ids_and_titles ]
    project = 'en.wikipedia'
    now = datetime.datetime.utcnow()

    # API call
    views_dict = pvc.article_views(project, articles, start=start, end=end)
    # transforming API call to rows (a list of tuples)
    daily_views = []
    for date in views_dict:
        for title in views_dict[date]:
            id, views = title_to_id[title], views_dict[date][title]
            daily_views.append((id, date, views, now, now))

    return daily_views


def insert_daily_snp500_wiki_views(conn, start=None, end=None):
    """
    Inserts wiki page views into the daily_views table

    Parameters:

        start (str) : YYYYMMDD, MMDDYYYY, DDMMYYYY
        end   (str) : YYYYMMDD, MMDDYYYY, DDMMYYYY
    """

    if start is None:
        start = (datetime.datetime.now() - timedelta(days=30))
        start = datetime.datetime.strftime(start, '%Y%m%d')
    else:
        start = parse_date_str(start)

    if end is None:
        end = datetime.datetime.now()
        end = datetime.datetime.strftime(end, '%Y%m%d')
    else:
        end = parse_date_str(end)

    print("Inserting dailywikipedia views price data from",
          start[:4]+'-'+start[4:6]+'-'+start[6:],
          end[:4]+'-'+end[4:6]+'-'+end[6:], sep=' ')
    if start == end:
        print("`daily_wiki_views` already up-to-date")
        return

    daily_views = _get_snp500_wiki_views(conn, start, end)
    columns_str = ("symbol_id, views_date, views, created_date, last_updated_date")
    fill_str = "%s, %s, %s, %s, %s"
    template_insert_str = ("INSERT IGNORE INTO daily_wiki_views ({columns})"
                          "VALUES ({vals})".format(columns=columns_str,
                                                   vals=fill_str))
    cur = conn.cursor()
    cur.executemany(template_insert_str, daily_views)
    cur.close()

