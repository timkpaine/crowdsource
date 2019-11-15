// tslint:disable: no-empty
import perspective from "@finos/perspective";
import {PerspectiveWidget, PerspectiveWorkspace} from "@finos/perspective-phosphor";
import {CommandRegistry} from "@phosphor/commands";
import {DockPanel, Menu, MenuBar, SplitPanel, Widget} from "@phosphor/widgets";
import {request, IRequestResult} from "requests-helper";
import {AdminWidget} from "./admin";
import {ADMIN, WSCOMPETITIONS} from "./define";
import {Header} from "./header";
import {SidebarPanel} from "./sidebar";
import {checkLoggedIn, loggedIn, basepath, wspath} from "./utils";
import {AboutWidget, APIKeysWidget, BaseWidget,
        CompetitionsWidget,
        LoginWidget, LogoutWidget, NewCompetitionWidget,
        NewSubmissionWidget, PaymentsWidget, RegisterWidget,
        SubmissionsWidget} from "./widgets";

import "@finos/perspective-viewer-d3fc";
import "@finos/perspective-viewer-hypergrid";

export const commands = new CommandRegistry();

export
async function main() {
    // see if logged in
    await checkLoggedIn();

    // connect to perspective
    const websocket = (perspective as any).websocket(wspath() + WSCOMPETITIONS);
    const table1 = websocket.open_table("competitions");
    const table2 = websocket.open_table("past_competitions");
    const table3 = websocket.open_table("submissions");

    // perspective workspace
    const workspace = new PerspectiveWorkspace();
    workspace.addClass("workspace");
    workspace.title.label = "Workspace";

    const widget1 = new PerspectiveWidget("Active Competitions");
    const widget2 = new PerspectiveWidget("Past Competitions");
    const widget3 = new PerspectiveWidget("Leaderboards");

    // top bar
    const header = new Header();
    // top right menu
    const menubar = new MenuBar();

    // configuration pages
    const about = new AboutWidget();
    const login = new LoginWidget();
    const logout = new LogoutWidget();
    const register = new RegisterWidget();

    const apikeys = new APIKeysWidget();
    const competitions = new CompetitionsWidget();
    const submissions = new SubmissionsWidget();
    const payments = new PaymentsWidget();

    const newcompetition = new NewCompetitionWidget();
    const newsubmission = new NewSubmissionWidget();

    const admin = new AdminWidget();

    // main container
    const mainPage = new SplitPanel({orientation: "horizontal"});
    const centerPage = new DockPanel();
    mainPage.addWidget(centerPage);
    centerPage.addWidget(workspace);

    // to track whats in side bar
    let sidePanel: BaseWidget = null;
    const closeWidget = (s: SidebarPanel) => {
        s.close();
        mainPage.setRelativeSizes([1]);
    };
    const sidebar = new SidebarPanel(closeWidget);

    // helper to clear sidebar
    const setSidePanel = (w: BaseWidget) => {
        // close currently open widget
        if (sidePanel) {
            sidePanel.close();
        }

        // add widget to sidebar
        sidebar.addWidget(w);

        // add sidebar to main page
        mainPage.addWidget(sidebar);

        // set to 3/1
        mainPage.setRelativeSizes([3, 1]);

        // set var to current widget
        sidePanel = w;
    };

    /*
     *  Commands
     */
    commands.addCommand("about", {
        execute: () => {setSidePanel(about); },
        iconClass: "fa fa-question",
        isEnabled: () => true,
        label: "About",
    });

    commands.addCommand("register", {
        execute: () => {setSidePanel(register); },
        iconClass: "fa fa-key",
        isEnabled: () => !loggedIn(),
        label: "Register",
    });

    commands.addCommand("login", {
        execute: () => {setSidePanel(login); },
        iconClass: "fa fa-sign-in",
        isEnabled: () => !loggedIn(),
        label: "Login",
    });

    commands.addCommand("logout", {
        execute: () => {setSidePanel(logout); },
        iconClass: "fa fa-sign-out",
        isEnabled: loggedIn,
        label: "Logout",
    });

    commands.addCommand("my:apikeys", {
        execute: () => {setSidePanel(apikeys); },
        iconClass: "fa fa-key",
        isEnabled: loggedIn,
        label: "API Keys",
    });

    commands.addCommand("my:competitions", {
        execute: () => {setSidePanel(competitions); },
        iconClass: "fa fa-hourglass-start",
        isEnabled: loggedIn,
        label: "Competitions",
    });

    commands.addCommand("my:submissions", {
        execute: () => {setSidePanel(submissions); },
        iconClass: "fa fa-paper-plane",
        isEnabled: loggedIn,
        label: "Submissions",
    });

    commands.addCommand("my:payments", {
        execute: () => {setSidePanel(payments); },
        iconClass: "fa fa-credit-card",
        isEnabled: loggedIn,
        label: "Wallet",
    });

    commands.addCommand("new:competition", {
        execute: () => {setSidePanel(newcompetition); },
        iconClass: "fa fa-plus",
        isEnabled: () => loggedIn(),
        label: "New Competition",
    });

    commands.addCommand("new:submission", {
        execute: () => {setSidePanel(newsubmission); },
        iconClass: "fa fa-plus",
        isEnabled: () => loggedIn(),
        label: "New Submission",
    });

    commands.addCommand("admin", {
        execute: () => {
            centerPage.addWidget(admin, {mode: "tab-before", ref: workspace});
            centerPage.selectWidget(admin);
        },
        iconClass: "fa fa-cog",
        isEnabled: () => loggedIn(),
        label: "Admin",
    });
    /*
     *  End commands
     */

    // Construct top menu
    menubar.addClass("topmenu");
    const menu = new Menu({commands});
    menu.addClass("settings");
    menu.title.label = "Settings";
    menu.title.mnemonic = 0;
    menu.addItem({ command: "about"});

    // login/register menu
    const lrmenu = new Menu({commands});
    lrmenu.addClass("settings");
    lrmenu.title.label = "Login/Register";
    lrmenu.addItem({ command: "register"});
    lrmenu.addItem({ command: "login"});
    lrmenu.addItem({ command: "logout"});
    menu.addItem({type: "submenu", submenu: lrmenu});

    // construct add menu
    const addmenu = new Menu({commands});
    addmenu.addClass("settings");
    addmenu.title.label = "New";
    addmenu.addItem({ command: "new:competition"});
    addmenu.addItem({ command: "new:submission"});
    menu.addItem({type: "submenu", submenu: addmenu});

    // construct profile menu
    const mymenu = new Menu({commands});
    mymenu.addClass("settings");
    mymenu.title.label = "Profile";
    mymenu.addItem({ command: "my:apikeys"});
    mymenu.addItem({ command: "my:competitions"});
    mymenu.addItem({ command: "my:submissions"});
    mymenu.addItem({ command: "my:payments"});
    menu.addItem({type: "submenu", submenu: mymenu});

    menubar.addMenu(menu);

    // get admin page
    request("get", basepath() + ADMIN).then((res: IRequestResult) => {
        if (res.ok) {
            menu.addItem({ command: "admin"});
        }
    });

    // Add tables to workspace
    workspace.addViewer(widget1, {});
    workspace.addViewer(widget2, {mode: "tab-after", ref: widget1});
    workspace.addViewer(widget3, {mode: "split-bottom", ref: widget1});

    // Attach parts to dom
    Widget.attach(header, document.body);
    Widget.attach(menubar, document.body);
    Widget.attach(mainPage, document.body);

    // Load perspective tables
    widget1.load(table1);
    widget2.load(table2);
    widget3.load(table3);

    window.onresize = () => {
        mainPage.update();
    };
    (window as any).workspace = workspace;
}
