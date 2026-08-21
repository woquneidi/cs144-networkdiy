#include<bits/stdc++.h>
using namespace std;
using i64 = long long;
int main() {
    freopen("baidu.txt", "r", stdin);
    freopen("baidu.out", "w", stdout);

    string s;
    double last = 0;
    int cnt;
    while (getline(cin, s)) {
        
        // cout << s << endl;
        string tmp;
        int ip = 0;
        for (int i = 0; i < s.length(); i++) {
            if (s[i] == ']') break;
            if (ip) tmp += s[i];
            if (s[i] == '[') ip = 1;

        }
        // cout << tmp << endl;
        if (tmp.size() == 0) continue;;
        double now = stod(tmp);
        cnt++;
        if (last) {
            // cout << now - last << endl;
            if (now - last > 0.25) cout << now << ' ' << cnt << ' ' << now - last << endl;
        }
        last = now;
    }
}